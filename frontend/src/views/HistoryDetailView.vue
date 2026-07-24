<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import Icon from '../components/Icon.vue'
import MaterialCard from '../components/MaterialCard.vue'
import SectionCard from '../components/SectionCard.vue'
import CaseCard from '../components/CaseCard.vue'
import ResearchStrip from '../components/ResearchStrip.vue'

const route = useRoute()
const router = useRouter()
const d = ref(null)
const err = ref('')
const materialRef = ref(null)
const caseRef = ref(null)

onMounted(async () => {
  try { d.value = await api.get('/api/consults/' + route.params.id) }
  catch (e) { err.value = e.message }
})

function onCite(c) {
  if (c.word === '材料') materialRef.value?.flash(c.n)
  else caseRef.value?.flashCase(c.n)
}
const secOrder = ['interpret', 'reply', 'method']
const statusMeta = { done: ['已完成', 'badge-green'], empty: ['无材料', 'badge-gray'], error: ['失败', 'badge-red'] }
</script>

<template>
  <div class="page detail">
    <button class="back" @click="router.back()"><Icon name="chevron" :size="14" style="transform:rotate(90deg)" />返回</button>
    <div v-if="err" class="card state-card">{{ err }}</div>
    <template v-else-if="d">
      <div class="card d-head">
        <div class="d-title-row">
          <h2>咨询详情 #{{ d.id }}</h2>
          <span class="badge" :class="statusMeta[d.status]?.[1]">{{ statusMeta[d.status]?.[0] || d.status }}</span>
          <span v-if="d.retrieval_mode === 'mock'" class="badge badge-amber">演示检索</span>
        </div>
        <p class="d-complaint">{{ d.complaint_text }}</p>
        <div class="d-meta">
          <span v-if="d.user">发起人：{{ d.user.display_name }}（{{ d.user.org || '—' }}）</span>
          <span>{{ d.created_at }}</span>
          <span v-if="d.service_area">地域：{{ d.service_area }}</span>
          <span v-if="d.latency_ms">耗时 {{ (d.latency_ms / 1000).toFixed(1) }}s</span>
          <span v-if="d.model">模型 {{ d.model }}</span>
        </div>
      </div>

      <ResearchStrip v-if="d.research" :research="d.research" :consult-id="d.id" readonly />

      <CaseCard v-if="d.cases?.length" ref="caseRef" :consult-id="d.id" :cases="d.cases"
                :experience-text="d.experience_text || ''" :experience-decision="d.decisions?.experience" readonly />

      <MaterialCard v-if="d.retrieval" ref="materialRef" :retrieval="d.retrieval" />

      <div v-if="d.status === 'empty'" class="card state-card">
        <h3>未检索到相关政策材料</h3><p>该次咨询因无可用材料而短路，未进行生成。</p>
      </div>
      <div v-if="d.status === 'error'" class="card state-card err"><h3>该次咨询失败</h3><p>{{ d.error_message }}</p></div>

      <div v-if="d.validation?.issues?.length" class="guard-strip">
        <Icon name="alert" :size="14" />
        <div><b>质量守卫提示</b><p v-for="(iss, i) in d.validation.issues" :key="i">{{ iss.detail }}</p></div>
      </div>

      <SectionCard v-for="name in secOrder" :key="name" :name="name" :consult-id="d.id"
                   :text="d.sections?.[name] || ''" :state="d.sections?.[name] ? 'done' : 'idle'"
                   :decision="d.decisions?.[name]" readonly @cite="onCite" />
    </template>
  </div>
</template>

<style scoped>
.detail { max-width: 860px; display: flex; flex-direction: column; gap: 14px; }
.back { display: inline-flex; align-items: center; gap: 4px; border: none; background: none; color: var(--ink-3); cursor: pointer; font-size: 13px; padding: 0; width: fit-content; }
.back:hover { color: var(--primary); }
.d-head { padding: 18px 20px; }
.d-title-row { display: flex; align-items: center; gap: 10px; }
.d-title-row h2 { font-family: var(--font-serif); font-size: 17px; }
.d-complaint { margin-top: 10px; font-size: 14px; background: var(--bg); border: 1px solid var(--line); border-radius: 8px; padding: 10px 14px; white-space: pre-wrap; }
.d-meta { display: flex; flex-wrap: wrap; gap: 14px; font-size: 12px; color: var(--ink-3); margin-top: 10px; }
.state-card { padding: 26px; text-align: center; color: var(--ink-2); }
.state-card h3 { font-family: var(--font-serif); margin-bottom: 6px; }
.state-card p { font-size: 13px; color: var(--ink-3); }
.state-card.err h3 { color: var(--red); }
.guard-strip { display: flex; gap: 10px; background: var(--amber-soft); border: 1px solid #eadfbf; border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: var(--amber); }
.guard-strip p { color: #7c5a10; margin-top: 2px; }
</style>
