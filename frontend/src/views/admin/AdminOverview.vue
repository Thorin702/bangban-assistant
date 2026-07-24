<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../api'

const router = useRouter()
const m = ref(null)
onMounted(async () => { m.value = await api.get('/api/admin/metrics') })

const SECTIONS = [['interpret', '条款解释'], ['reply', '回复话术'], ['method', '办理方法'], ['experience', '类案经验']]

const adoption = computed(() => {
  if (!m.value) return []
  return SECTIONS.map(([key, label]) => {
    const d = m.value.decisions[key] || {}
    const adopt = d.adopt || 0, modify = d.modify || 0, reject = d.reject || 0
    const total = adopt + modify + reject
    return { key, label, adopt, modify, reject, total,
      rate: total ? Math.round(((adopt + modify) / total) * 100) : null }
  })
})
const dailyMax = computed(() => Math.max(1, ...(m.value?.daily || []).map((d) => d.count)))

const stats = computed(() => m.value ? [
  { label: '累计咨询', value: m.value.total_consults },
  { label: '近7天咨询', value: m.value.week_consults },
  { label: '近7天活跃用户', value: m.value.active_users_7d },
  { label: '平均首字耗时', value: m.value.avg_first_token_ms ? (m.value.avg_first_token_ms / 1000).toFixed(1) + 's' : '—' },
  { label: '空结果率', value: (m.value.empty_rate * 100).toFixed(1) + '%', hint: '未检索到材料而诚实短路的占比' },
  { label: '守卫违规率', value: (m.value.violation_rate * 100).toFixed(1) + '%', hint: '生成后自动校验发现问题的占比', warn: m.value.violation_rate > 0.1 },
] : [])
</script>

<template>
  <div class="ov" v-if="m">
    <div class="stat-grid">
      <div v-for="s in stats" :key="s.label" class="card stat" :title="s.hint || ''">
        <div class="stat-value" :class="{ warn: s.warn }">{{ s.value }}</div>
        <div class="stat-label">{{ s.label }}</div>
      </div>
    </div>

    <div class="two-col">
      <div class="card panel">
        <h3>近 14 天咨询量</h3>
        <div class="bars" v-if="m.daily.length">
          <div v-for="d in m.daily" :key="d.date" class="bar-col" :title="d.date + '：' + d.count">
            <div class="bar" :style="{ height: Math.max(6, (d.count / dailyMax) * 110) + 'px' }" />
            <span class="bar-x">{{ d.date.slice(5) }}</span>
          </div>
        </div>
        <p v-else class="empty-hint">暂无数据</p>
      </div>

      <div class="card panel">
        <h3>分段采纳情况 <span class="panel-note">采纳+修改 视为有效 · 内部质量信号，不用于考核</span></h3>
        <div v-for="a in adoption" :key="a.key" class="adopt-row">
          <span class="adopt-label">{{ a.label }}</span>
          <div class="adopt-bar">
            <template v-if="a.total">
              <div class="seg seg-a" :style="{ width: (a.adopt / a.total) * 100 + '%' }" :title="'采纳 ' + a.adopt" />
              <div class="seg seg-m" :style="{ width: (a.modify / a.total) * 100 + '%' }" :title="'修改后采纳 ' + a.modify" />
              <div class="seg seg-r" :style="{ width: (a.reject / a.total) * 100 + '%' }" :title="'拒绝 ' + a.reject" />
            </template>
            <div v-else class="seg-empty">暂无决策</div>
          </div>
          <span class="adopt-rate">{{ a.rate === null ? '—' : a.rate + '%' }}</span>
        </div>
        <div class="legend">
          <span><i class="dot seg-a" />采纳</span><span><i class="dot seg-m" />修改后采纳</span><span><i class="dot seg-r" />拒绝</span>
        </div>
      </div>
    </div>

    <div class="card panel">
      <h3>最近质量守卫异常 <span class="panel-note">共 {{ m.violation_count }} 条 · 点击可查看该次咨询</span></h3>
      <table class="table" v-if="m.recent_violations.length">
        <thead><tr><th style="width:90px">咨询</th><th style="width:160px">时间</th><th>问题</th></tr></thead>
        <tbody>
          <tr v-for="v in m.recent_violations" :key="v.consult_id" class="v-row" @click="router.push('/history/' + v.consult_id)">
            <td>#{{ v.consult_id }}</td>
            <td>{{ v.created_at }}</td>
            <td><div v-for="(iss, i) in v.issues" :key="i" class="v-issue">{{ iss.detail }}</div></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty-hint">暂无异常，生成质量良好</p>
    </div>
  </div>
  <div v-else class="card" style="padding: 24px"><div class="skeleton" style="height: 120px" /></div>
</template>

<style scoped>
.ov { display: flex; flex-direction: column; gap: 16px; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.stat { padding: 16px 18px; }
.stat-value { font-size: 24px; font-weight: 700; font-family: var(--font-serif); color: var(--ink); }
.stat-value.warn { color: var(--amber); }
.stat-label { font-size: 12px; color: var(--ink-3); margin-top: 2px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 900px) { .two-col { grid-template-columns: 1fr; } }
.panel { padding: 16px 18px; }
.panel h3 { font-size: 14px; font-family: var(--font-serif); margin-bottom: 14px; }
.panel-note { font-size: 11.5px; color: var(--ink-3); font-weight: 400; font-family: var(--font-sans); margin-left: 8px; }
.bars { display: flex; align-items: flex-end; gap: 6px; height: 140px; padding-top: 8px; }
.bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; justify-content: flex-end; }
.bar { width: 100%; max-width: 30px; background: linear-gradient(180deg, #3a6cb0, var(--primary)); border-radius: 4px 4px 0 0; }
.bar-x { font-size: 10px; color: var(--ink-3); transform: scale(.9); }
.adopt-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.adopt-label { width: 62px; font-size: 12.5px; color: var(--ink-2); flex: none; }
.adopt-bar { flex: 1; height: 16px; border-radius: 5px; overflow: hidden; display: flex; background: var(--bg-deep); }
.seg { height: 100%; }
.seg-a { background: var(--green); }
.seg-m { background: #4a7fc1; }
.seg-r { background: #c9c5b8; }
.seg-empty { font-size: 11px; color: var(--ink-3); padding: 0 8px; line-height: 16px; }
.adopt-rate { width: 44px; text-align: right; font-size: 12.5px; font-weight: 600; color: var(--ink-2); flex: none; }
.legend { display: flex; gap: 14px; font-size: 11.5px; color: var(--ink-3); margin-top: 4px; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 4px; }
.v-row { cursor: pointer; }
.v-issue { font-size: 12.5px; color: var(--amber); }
.empty-hint { font-size: 13px; color: var(--ink-3); padding: 12px 0; }
</style>
