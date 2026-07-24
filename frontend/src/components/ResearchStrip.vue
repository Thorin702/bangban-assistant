<script setup>
import { onUnmounted, ref } from 'vue'
import Icon from './Icon.vue'
import { ssePost } from '../api'

const props = defineProps({
  research: Object,          // {sample_n, deadline, satisfaction, related}
  consultId: Number,
  readonly: Boolean,
})

const open = ref('')        // 当前展开的信号：'' | 'deadline' | 'satisfaction' | 'related'
const rxText = ref('')      // 满意度处方全文
const rxState = ref('idle') // idle | streaming | done | error
const rxErr = ref('')

function toggle(key) {
  open.value = open.value === key ? '' : key
  if (key === 'satisfaction' && open.value === 'satisfaction' && rxState.value === 'idle' && !props.readonly) {
    fetchRx()
  }
}

let rxAbort = null
async function fetchRx() {
  rxState.value = 'streaming'; rxText.value = ''; rxErr.value = ''
  const { promise, abort } = ssePost(`/api/consults/${props.consultId}/prescription`, {}, (event, data) => {
    if (event === 'delta') rxText.value += data.text
    else if (event === 'error') { rxErr.value = data.message; rxState.value = 'error' }
    else if (event === 'done') rxState.value = 'done'
  })
  rxAbort = abort
  try { await promise } catch (e) { rxErr.value = e.message; rxState.value = 'error' }
  rxAbort = null
  if (rxState.value === 'streaming') rxState.value = 'done'
}
onUnmounted(() => { rxAbort?.() })

const pct = (x) => Math.round(x * 100)
const dlClass = (lv) => ({ high: 'sig-red', mid: 'sig-amber', low: 'sig-green' }[lv] || 'sig-gray')
const satClass = (lv) => ({ high: 'sig-green', mid: 'sig-amber', low: 'sig-red' }[lv] || 'sig-gray')
const relClass = (lv) => ({ high: 'sig-red', mid: 'sig-amber' }[lv] || 'sig-gray')
</script>

<template>
  <div v-if="research" class="rstrip">
    <div class="rstrip-row">
      <span class="rstrip-tag">办件研判</span>

      <button v-if="research.deadline" class="sig" :class="[dlClass(research.deadline.level), { on: open==='deadline' }]" @click="toggle('deadline')">
        <Icon name="clock" :size="13" />
        <b>时限</b>同类均 {{ research.deadline.median_days }} 天 · 超期 {{ pct(research.deadline.overdue_rate) }}%
        <Icon name="chevron" :size="12" class="caret" :class="{ up: open==='deadline' }" />
      </button>

      <button v-if="research.satisfaction" class="sig" :class="[satClass(research.satisfaction.level), { on: open==='satisfaction' }]" @click="toggle('satisfaction')">
        <Icon name="check" :size="13" />
        <b>满意度</b>同类 {{ pct(research.satisfaction.rate) }}% · 处方
        <Icon name="chevron" :size="12" class="caret" :class="{ up: open==='satisfaction' }" />
      </button>

      <button v-if="research.related" class="sig" :class="[relClass(research.related.level), { on: open==='related' }]" @click="toggle('related')">
        <Icon name="alert" :size="13" />
        <b>关联</b>本小区历史同类 {{ research.related.count }} 件
        <Icon name="chevron" :size="12" class="caret" :class="{ up: open==='related' }" />
      </button>

      <span class="rstrip-note">基于 {{ research.sample_n }} 件同类历史工单</span>
    </div>

    <!-- 时限详情 -->
    <div v-if="open==='deadline'" class="rdetail">
      同类工单办结中位 <b>{{ research.deadline.median_days }} 天</b>，超期率 <b>{{ pct(research.deadline.overdue_rate) }}%</b>（样本 {{ research.deadline.n }} 件）。
      <span v-if="research.deadline.level==='high'" class="warn">同类超期偏多，建议尽早现场核实并首次反馈，留足办理时间。</span>
      <span v-else>建议在办理时限内完成现场核实与首次答复。</span>
    </div>

    <!-- 满意度处方 -->
    <div v-if="open==='satisfaction'" class="rdetail">
      <div class="rx-head">同类满意率 <b>{{ pct(research.satisfaction.rate) }}%</b>（{{ research.satisfaction.n }} 件，其中不满意 {{ research.satisfaction.unsat_n }} 件）·
        <span class="rx-tag">经验参考，不代表政策口径</span></div>
      <div v-if="readonly && !rxText" class="rx-hint">（历史记录不含处方，可在新咨询中查看）</div>
      <div v-else-if="rxState==='error'" class="rx-err">{{ rxErr }}</div>
      <div v-else-if="rxState==='streaming' && !rxText" class="rx-hint"><span class="spin" />正在从同类满意/不满意案例中提炼…</div>
      <div v-else class="rx-body">
        <template v-for="(line, i) in rxText.split('\n')" :key="i">
          <div v-if="line.trim().startsWith('【')" class="rx-sec">{{ line.trim() }}</div>
          <div v-else-if="line.trim()" class="rx-line">{{ line.trim() }}</div>
        </template>
        <span v-if="rxState==='streaming'" class="stream-cursor" />
      </div>
    </div>

    <!-- 关联详情 -->
    <div v-if="open==='related'" class="rdetail">
      <div class="rel-head">
        <b>{{ research.related.community }}</b> 历史同类诉求 <b>{{ research.related.count }}</b> 件
        <span v-if="research.related.level==='high'" class="warn">· 疑似重复投诉/老大难点，建议核查能否并案或系统性解决</span>
      </div>
      <ul class="rel-list">
        <li v-for="(c, i) in research.related.cases" :key="i">
          <span class="rel-date">{{ c.entry_date }}</span>
          <span class="rel-txt">{{ c.complaint }}</span>
          <span v-if="c.is_satisfied" class="rel-badge">{{ c.is_satisfied }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.rstrip { background: #fbfaf7; border: 1px solid var(--line); border-radius: 10px; padding: 8px 12px; }
.rstrip-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rstrip-tag { font-size: 11.5px; color: var(--ink-3); font-weight: 500; padding-right: 2px; }
.sig {
  display: inline-flex; align-items: center; gap: 5px; cursor: pointer;
  border: 1px solid transparent; border-radius: 999px; padding: 4px 10px;
  font-size: 12.5px; background: #fff; transition: all .12s; white-space: nowrap;
}
.sig b { font-weight: 600; margin-right: 1px; }
.sig .caret { transition: transform .15s; opacity: .6; }
.sig .caret.up { transform: rotate(180deg); }
.sig.on { box-shadow: 0 0 0 2px rgba(0,0,0,.04) inset; }
.sig-green { color: var(--green); border-color: #cbe2d5; background: var(--green-soft); }
.sig-amber { color: var(--amber); border-color: #eadfbf; background: var(--amber-soft); }
.sig-red { color: var(--red); border-color: #e5c5c5; background: var(--red-soft); }
.sig-gray { color: var(--ink-2); border-color: var(--line-strong); }
.rstrip-note { font-size: 11.5px; color: var(--ink-3); margin-left: auto; }

.rdetail { margin-top: 8px; padding: 10px 12px; background: #fff; border: 1px solid var(--line); border-radius: 8px; font-size: 13px; color: var(--ink-2); line-height: 1.7; animation: fade .18s ease; }
@keyframes fade { from { opacity: 0; transform: translateY(-3px); } }
.warn { color: var(--red); }
.rx-head { font-size: 12.5px; color: var(--ink-3); margin-bottom: 8px; }
.rx-head b { color: var(--ink); }
.rx-tag { color: var(--amber); background: var(--amber-soft); padding: 1px 7px; border-radius: 999px; font-size: 11px; }
.rx-hint { color: var(--ink-3); font-size: 12.5px; display: flex; align-items: center; gap: 8px; }
.rx-err { color: var(--red); font-size: 12.5px; }
.rx-sec { font-weight: 600; color: var(--primary); margin-top: 6px; }
.rx-line { padding-left: 4px; }
.rel-head { margin-bottom: 6px; }
.rel-list { margin: 0; padding-left: 0; list-style: none; }
.rel-list li { display: flex; gap: 8px; align-items: baseline; padding: 4px 0; border-top: 1px dashed var(--line); font-size: 12.5px; }
.rel-date { color: var(--ink-3); flex: none; font-variant-numeric: tabular-nums; }
.rel-txt { color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rel-badge { flex: none; color: var(--ink-3); font-size: 11px; }
.spin { width: 12px; height: 12px; border: 2px solid var(--line-strong); border-top-color: var(--primary); border-radius: 50%; animation: rot .8s linear infinite; display: inline-block; }
@keyframes rot { to { transform: rotate(360deg); } }
</style>
