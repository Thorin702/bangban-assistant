<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { store } from '../store'
import { ssePost } from '../api'
import { toast } from '../toast'
import Icon from '../components/Icon.vue'
import MaterialCard from '../components/MaterialCard.vue'
import SectionCard from '../components/SectionCard.vue'
import CaseCard from '../components/CaseCard.vue'
import ResearchStrip from '../components/ResearchStrip.vue'

const form = reactive({ complaint_text: '' })
const materialRef = ref(null)
const caseRef = ref(null)
const complaintRef = ref(null)

function autoGrow() {
  const el = complaintRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 320) + 'px'
}
watch(() => form.complaint_text, () => nextTick(autoGrow))
onMounted(autoGrow)

const run = reactive({
  phase: 'idle',
  consultId: null,
  retrieval: null,
  cases: [],
  research: null,
  sections: { interpret: '', reply: '', method: '', raw: '' },
  sectionState: { interpret: 'idle', reply: 'idle', method: 'idle' },
  decisions: {},
  validation: null,
  error: null,
  latency: null,
})
let abortFn = null

const cfg = computed(() => store.config || {})
const canSubmit = computed(() => form.complaint_text.trim().length >= 10 && run.phase !== 'retrieving' && run.phase !== 'generating')

function resetRun() {
  Object.assign(run, {
    phase: 'idle', consultId: null, retrieval: null, cases: [], research: null,
    sections: { interpret: '', reply: '', method: '', raw: '' },
    sectionState: { interpret: 'idle', reply: 'idle', method: 'idle' },
    decisions: {}, validation: null, error: null, latency: null,
  })
}

async function submit() {
  if (!canSubmit.value) return
  resetRun()
  run.phase = 'retrieving'
  const { promise, abort } = ssePost('/api/consults', { complaint_text: form.complaint_text.trim() }, onEvent)
  abortFn = abort
  try { await promise } catch (e) {
    if (!['done', 'empty', 'error'].includes(run.phase)) {
      run.phase = 'error'
      run.error = { message: e.message, retryable: true }
    }
  }
  abortFn = null
  // 兜底：连接正常结束但未收到 done 事件时，不让界面卡在"生成中"
  if (['retrieving', 'generating'].includes(run.phase)) {
    for (const k of Object.keys(run.sectionState)) if (run.sectionState[k] === 'streaming') run.sectionState[k] = 'done'
    run.phase = 'done'
  }
}

onUnmounted(() => { abortFn?.() })

function onEvent(event, data) {
  if (event === 'meta') run.consultId = data.consult_id
  else if (event === 'cases') run.cases = data.cases
  else if (event === 'research') run.research = data
  else if (event === 'retrieval') { run.retrieval = data; run.phase = 'generating' }
  else if (event === 'empty') run.phase = 'empty'
  else if (event === 'section') {
    if (data.name in run.sectionState) run.sectionState[data.name] = data.status === 'start' ? 'streaming' : 'done'
  } else if (event === 'delta') {
    if (data.name in run.sections) run.sections[data.name] += data.text
    else run.sections.raw += data.text
  } else if (event === 'validation') run.validation = data
  else if (event === 'done') {
    run.phase = 'done'
    run.latency = data.latency_ms
    for (const k of Object.keys(run.sectionState)) if (run.sectionState[k] === 'streaming') run.sectionState[k] = 'done'
  } else if (event === 'error') { run.phase = 'error'; run.error = data }
}

function cancel() {
  if (abortFn) { abortFn(); toast('已中断生成', 'warn') }
  run.phase = run.retrieval ? 'done' : 'idle'
  for (const k of Object.keys(run.sectionState)) if (run.sectionState[k] === 'streaming') run.sectionState[k] = 'done'
}

function onCite(c) {
  if (c.word === '材料') materialRef.value?.flash(c.n)
  else caseRef.value?.flashCase(c.n)
}
function onDecided({ section, decision, modified_text, reason }) {
  if (decision === null) { delete run.decisions[section]; return }
  run.decisions[section] = { decision, modified_text, reason, created_at: '' }
}

const sectionOrder = ['reply', 'method', 'interpret']
const generating = computed(() => run.phase === 'generating')
const showResult = computed(() => run.phase !== 'idle')
const hasSectionText = computed(() => !!(run.sections.reply || run.sections.method || run.sections.interpret))
const genLoading = computed(() => run.phase === 'retrieving' || (run.phase === 'generating' && !hasSectionText.value))
const hasMaterials = computed(() => run.retrieval && run.retrieval.materials.length > 0)

const EXAMPLES = [
  '小区供暖不热，室温只有14度，物业和热力公司互相推诿，居民要求测温退费。',
  '来电人在工地做木工，包工头拖欠8名工人工资2万余元，负责人电话已不接，要求协调支付。',
  '楼上邻居家漏水导致我家墙面被泡，多次协商拒不维修，物业称管不了，如何处理？',
]
function useExample(t) { form.complaint_text = t }

function newConsult() {
  if (abortFn) abortFn()
  abortFn = null
  form.complaint_text = ''
  resetRun()
  nextTick(() => { autoGrow(); complaintRef.value?.focus() })
}
</script>

<template>
  <div class="page consult">
    <aside class="left">
      <div class="card input-card">
        <div class="input-head">
          <h2 class="input-title">智能办理</h2>
          <button v-if="showResult || form.complaint_text" class="new-btn" @click="newConsult" title="清空并开启新咨询">
            <Icon name="plus" :size="13" />新咨询
          </button>
        </div>
        <p class="input-sub">
          粘贴工单或纠纷描述，生成可核实的政策参考
          <span v-if="cfg.service_area" class="area-chip">适用地域 · {{ cfg.service_area }}</span>
        </p>
        <textarea
          ref="complaintRef" class="textarea complaint-input" v-model="form.complaint_text" rows="2" :maxlength="2000"
          placeholder="例：来电人反映，滕州市某小区供暖不热，室温仅14度，多次反映物业与热力公司互相推诿，要求测温并退还部分供暖费……"
          @input="autoGrow" @keydown.ctrl.enter="submit" @keydown.meta.enter="submit"
        />
        <div class="input-meta">
          <span :class="{ warn: form.complaint_text.length > 1900 }">{{ form.complaint_text.length }}/2000</span>
          <span class="kbd-hint">Ctrl + Enter 提交</span>
        </div>
        <button v-if="!generating && run.phase !== 'retrieving'" class="btn btn-primary submit-btn" :disabled="!canSubmit" @click="submit">
          <Icon name="send" :size="15" />生成参考
        </button>
        <button v-else class="btn btn-plain submit-btn" @click="cancel">
          <span class="spin" />生成中，点击可中断
        </button>
        <p v-if="cfg.llm_ready === false" class="llm-warn">
          <Icon name="alert" :size="13" />生成模型尚未配置，请管理员在「后台管理 → 生成模型接入」中完成配置
        </p>
      </div>

      <div v-if="run.phase === 'idle'" class="example-card">
        <div class="example-title">试试真实场景</div>
        <button v-for="(e, i) in EXAMPLES" :key="i" class="example-item" @click="useExample(e)">{{ e }}</button>
      </div>
    </aside>

    <section class="right">
      <div class="disclaimer">
        <Icon name="shield" :size="14" />
        <span>{{ cfg.disclaimer_text || 'AI 生成内容仅供参考，请人工核实后使用' }}</span>
        <span v-if="run.latency" class="latency">本次耗时 {{ (run.latency / 1000).toFixed(1) }}s</span>
      </div>

      <div v-if="!showResult" class="welcome card">
        <div class="welcome-steps">
          <div class="wstep"><span class="wnum">1</span><div><b>粘贴诉求</b><p>工单原文或纠纷描述，无需整理格式</p></div></div>
          <div class="wstep"><span class="wnum">2</span><div><b>生成参考</b><p>政策引用秒级返回，解释·话术·办法流式生成</p></div></div>
          <div class="wstep"><span class="wnum">3</span><div><b>人工核实后使用</b><p>逐部分采纳/修改/拒绝，全程留痕可追溯</p></div></div>
        </div>
        <div class="welcome-foot">
          <span v-if="cfg.case_feature_enabled" class="badge badge-green">类案经验已开启</span>
          <span>每条关键信息都带 <span class="cite-chip" style="cursor:default">材1</span> 角标，点击可回到政策原文</span>
        </div>
      </div>

      <template v-else>
        <!-- 办件研判条（细条·点击展开，置结果区顶部）-->
        <ResearchStrip v-if="cfg.research_enabled && run.research" :research="run.research" :consult-id="run.consultId" />

        <!-- 质量守卫提示（置顶） -->
        <div v-if="run.validation?.issues?.length" class="guard-strip">
          <Icon name="alert" :size="14" />
          <div>
            <b>质量守卫提示（{{ run.validation.issues.length }}）</b>
            <p v-for="(iss, i) in run.validation.issues" :key="i">{{ iss.detail }}</p>
          </div>
        </div>

        <!-- 生成中占位（内容自上而下填充）-->
        <div v-if="genLoading" class="card gen-loading">
          <span class="spin" /><span>正在检索政策并生成参考，请稍候…</span>
        </div>

        <!-- 一线优先看：回复话术 / 办理方法 / 条款解释 -->
        <SectionCard v-for="name in sectionOrder" :key="name" :name="name"
                     :consult-id="run.consultId" :text="run.sections[name]"
                     :state="run.sectionState[name]" :decision="run.decisions[name]"
                     @cite="onCite" @decided="onDecided" />

        <div v-if="run.sections.raw.trim()" class="card raw-card">
          <div class="raw-head"><Icon name="alert" :size="14" />格式异常内容（未能按三部分切分）</div>
          <pre>{{ run.sections.raw }}</pre>
        </div>

        <!-- 空态 / 错误态 -->
        <div v-if="run.phase === 'empty'" class="card state-card">
          <Icon name="search" :size="22" />
          <h3>未检索到相关政策材料</h3>
          <p>为避免无依据的生成，本次不输出参考内容。建议：换更具体的关键词（事项、对象、地域）重试，或转人工渠道核实。</p>
        </div>
        <div v-if="run.phase === 'error'" class="card state-card err">
          <Icon name="alert" :size="22" />
          <h3>{{ run.error?.stage === 'retrieval' ? '政策检索失败' : '生成失败' }}</h3>
          <p>{{ run.error?.message }}</p>
          <button v-if="run.error?.retryable" class="btn btn-ghost" @click="submit"><Icon name="refresh" :size="14" />重试</button>
        </div>

        <!-- 依据：政策引用（可展开核实）-->
        <MaterialCard v-if="hasMaterials || run.phase === 'retrieving'" ref="materialRef"
                      :retrieval="run.retrieval" :loading="run.phase === 'retrieving'" />

        <!-- 类案参考（历史经验，置底）-->
        <CaseCard v-if="cfg.case_feature_enabled && run.cases.length" ref="caseRef"
                  :consult-id="run.consultId" :cases="run.cases"
                  :experience-decision="run.decisions.experience" @decided="onDecided" />
      </template>
    </section>
  </div>
</template>

<style scoped>
.consult { display: grid; grid-template-columns: 390px 1fr; gap: 20px; align-items: start; }
@media (max-width: 960px) { .consult { grid-template-columns: 1fr; } .left { position: static !important; } }
.left { position: sticky; top: 76px; }
.input-card { padding: 20px 20px 18px; }
.input-head { display: flex; align-items: center; justify-content: space-between; }
.input-title { font-family: var(--font-serif); font-size: 18px; }
.new-btn {
  display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--primary-line);
  background: var(--primary-soft); color: var(--primary); border-radius: 999px;
  padding: 4px 12px; font-size: 12.5px; cursor: pointer; transition: all .15s;
}
.new-btn:hover { background: var(--primary); color: #fff; }
.input-sub { font-size: 12.5px; color: var(--ink-3); margin: 4px 0 14px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.area-chip { background: var(--primary-soft); color: var(--primary); padding: 2px 8px; border-radius: 999px; font-size: 11.5px; }
.complaint-input { min-height: 60px; max-height: 320px; font-size: 14px; overflow-y: auto; transition: height .1s ease; }
.gen-loading { display: flex; align-items: center; gap: 10px; padding: 16px 18px; font-size: 13.5px; color: var(--ink-3); }
.input-meta { display: flex; justify-content: space-between; font-size: 11.5px; color: var(--ink-3); margin-top: 6px; }
.input-meta .warn { color: var(--amber); }
.submit-btn { width: 100%; margin-top: 16px; height: 40px; font-size: 15px; }
.spin { width: 14px; height: 14px; border: 2px solid var(--line-strong); border-top-color: var(--primary); border-radius: 50%; animation: rot .8s linear infinite; }
@keyframes rot { to { transform: rotate(360deg); } }
.llm-warn { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--amber); margin-top: 10px; }
.example-card { margin-top: 14px; padding: 4px 2px; }
.example-title { font-size: 12.5px; color: var(--ink-3); margin: 8px 6px; }
.example-item {
  display: block; width: 100%; text-align: left; background: none; cursor: pointer;
  border: 1px dashed var(--line-strong); border-radius: 10px; padding: 10px 12px;
  color: var(--ink-2); font-size: 13px; margin-bottom: 8px; line-height: 1.6; transition: all .15s;
}
.example-item:hover { border-color: var(--primary); color: var(--primary); background: var(--primary-soft); }
.right { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.disclaimer {
  display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--amber);
  background: var(--amber-soft); border: 1px solid #eadfbf; border-radius: 10px; padding: 8px 14px;
}
.latency { margin-left: auto; color: var(--ink-3); }
.welcome { padding: 30px 28px; }
.welcome-steps { display: flex; gap: 26px; flex-wrap: wrap; }
.wstep { display: flex; gap: 12px; flex: 1; min-width: 180px; }
.wnum {
  flex: none; width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center;
  background: var(--primary-soft); color: var(--primary); font-weight: 700; font-family: var(--font-serif); font-size: 16px;
}
.wstep b { font-size: 14.5px; }
.wstep p { font-size: 12.5px; color: var(--ink-3); margin-top: 3px; }
.welcome-foot { display: flex; align-items: center; gap: 12px; margin-top: 24px; padding-top: 16px; border-top: 1px dashed var(--line); font-size: 12.5px; color: var(--ink-3); flex-wrap: wrap; }
.state-card { padding: 30px; text-align: center; color: var(--ink-2); }
.state-card svg { color: var(--ink-3); }
.state-card h3 { font-family: var(--font-serif); margin: 10px 0 6px; }
.state-card p { font-size: 13px; color: var(--ink-3); max-width: 480px; margin: 0 auto 12px; }
.state-card.err svg, .state-card.err h3 { color: var(--red); }
.guard-strip {
  display: flex; gap: 10px; background: var(--amber-soft); border: 1px solid #eadfbf;
  border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: var(--amber);
}
.guard-strip b { font-size: 12.5px; }
.guard-strip p { color: #7c5a10; margin-top: 2px; }
.raw-card { padding: 14px 18px; }
.raw-head { display: flex; align-items: center; gap: 6px; color: var(--amber); font-size: 13px; font-weight: 500; margin-bottom: 8px; }
.raw-card pre { white-space: pre-wrap; font-family: inherit; font-size: 13.5px; margin: 0; }
</style>
