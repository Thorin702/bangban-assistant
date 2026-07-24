<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'

const router = useRouter()
const data = ref(null)
const page = ref(1)
const loading = ref(false)

async function load() {
  loading.value = true
  try { data.value = await api.get(`/api/consults?page=${page.value}&size=15`) }
  finally { loading.value = false }
}
onMounted(load)
function go(p) { page.value = p; load() }

const statusMeta = {
  done: ['已完成', 'badge-green'], empty: ['无材料', 'badge-gray'],
  error: ['失败', 'badge-red'], running: ['进行中', 'badge-blue'],
}
const secName = { interpret: '解释', reply: '话术', method: '办法', experience: '经验' }
const decClass = { adopt: 'dd-adopt', modify: 'dd-modify', reject: 'dd-reject' }
</script>

<template>
  <div class="page history">
    <div class="h-head">
      <h2>历史记录</h2>
      <p>本人发起的咨询与决策留痕，点击可回看完整产出</p>
    </div>

    <div class="card">
      <div v-if="loading && !data" class="h-loading"><div class="skeleton" style="height: 48px" v-for="i in 5" :key="i" /></div>
      <template v-else-if="data">
        <div v-if="!data.items.length" class="h-empty">
          <Icon name="history" :size="24" />
          <p>还没有咨询记录，去<a @click.prevent="router.push('/')" href="#">发起第一次咨询</a></p>
        </div>
        <div v-else>
          <div v-for="it in data.items" :key="it.id" class="h-row" @click="router.push('/history/' + it.id)">
            <div class="h-main">
              <p class="h-excerpt">{{ it.excerpt }}</p>
              <div class="h-meta">
                <span>{{ it.created_at }}</span>
                <span v-if="it.service_area">{{ it.service_area }}</span>
                <span v-if="it.latency_ms">{{ (it.latency_ms / 1000).toFixed(1) }}s</span>
              </div>
            </div>
            <div class="h-side">
              <div class="h-decs">
                <span v-for="(d, s) in it.decisions" :key="s" class="h-dec" :class="decClass[d]">{{ secName[s] }}</span>
              </div>
              <span class="badge" :class="statusMeta[it.status]?.[1]">{{ statusMeta[it.status]?.[0] || it.status }}</span>
              <Icon name="chevron" :size="15" style="transform: rotate(-90deg); color: var(--ink-3)" />
            </div>
          </div>
          <div class="h-pager" v-if="data.total > data.size">
            <button class="btn btn-plain btn-sm" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
            <span>{{ page }} / {{ Math.ceil(data.total / data.size) }}</span>
            <button class="btn btn-plain btn-sm" :disabled="page >= Math.ceil(data.total / data.size)" @click="go(page + 1)">下一页</button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.history { max-width: 860px; }
.h-head { margin-bottom: 16px; }
.h-head h2 { font-family: var(--font-serif); font-size: 20px; }
.h-head p { font-size: 12.5px; color: var(--ink-3); margin-top: 4px; }
.h-loading { padding: 16px; display: flex; flex-direction: column; gap: 10px; }
.h-empty { padding: 48px; text-align: center; color: var(--ink-3); font-size: 13.5px; }
.h-empty p { margin-top: 8px; }
.h-row {
  display: flex; align-items: center; gap: 14px; padding: 14px 18px;
  border-bottom: 1px solid var(--line); cursor: pointer; transition: background .12s;
}
.h-row:hover { background: #fbfaf7; }
.h-row:last-of-type { border-bottom: none; }
.h-main { flex: 1; min-width: 0; }
.h-excerpt { font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.h-meta { display: flex; gap: 12px; font-size: 12px; color: var(--ink-3); margin-top: 4px; }
.h-side { display: flex; align-items: center; gap: 10px; flex: none; }
.h-decs { display: flex; gap: 4px; }
.h-dec { font-size: 11px; padding: 2px 6px; border-radius: 5px; }
.dd-adopt { background: var(--green-soft); color: var(--green); }
.dd-modify { background: var(--primary-soft); color: var(--primary); }
.dd-reject { background: var(--bg-deep); color: var(--ink-3); }
.h-pager { display: flex; align-items: center; justify-content: center; gap: 14px; padding: 14px; font-size: 13px; color: var(--ink-3); }
@media (max-width: 720px) { .h-decs { display: none; } }
</style>
