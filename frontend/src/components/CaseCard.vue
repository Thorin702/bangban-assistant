<script setup>
import { onUnmounted, ref } from 'vue'
import Icon from './Icon.vue'
import CitedText from './CitedText.vue'
import Modal from './Modal.vue'
import { api, ssePost } from '../api'
import { toast } from '../toast'

const props = defineProps({
  consultId: Number,
  cases: Array,
  experienceText: { type: String, default: '' },   // 历史详情回放用
  experienceDecision: Object,
  readonly: Boolean,
})
const emit = defineEmits(['decided'])

const open = ref({})
const expText = ref(props.experienceText || '')
const expState = ref(props.experienceText ? 'done' : 'idle')  // idle|streaming|done|error
const expError = ref('')
const busy = ref(false)
const showReject = ref(false)
const rejectReason = ref('与本案情形不符')

function flashCase(n) {
  const el = document.getElementById('case-' + n)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.classList.remove('flash-target'); void el.offsetWidth; el.classList.add('flash-target')
}
defineExpose({ flashCase })

let expAbort = null
async function extract() {
  expState.value = 'streaming'
  expText.value = ''
  expError.value = ''
  const { promise, abort } = ssePost(`/api/consults/${props.consultId}/experience`, {}, (event, data) => {
    if (event === 'delta') expText.value += data.text
    else if (event === 'error') { expError.value = data.message; expState.value = 'error' }
    else if (event === 'done') expState.value = 'done'
  })
  expAbort = abort
  try { await promise } catch (e) { expError.value = e.message; expState.value = 'error' }
  expAbort = null
  if (expState.value === 'streaming') expState.value = 'done'
}
onUnmounted(() => { expAbort?.() })

async function decide(decision, extra = {}) {
  busy.value = true
  try {
    await api.post(`/api/consults/${props.consultId}/decisions`, { section: 'experience', decision, ...extra })
    emit('decided', { section: 'experience', decision, ...extra })
    toast('已记录', 'ok')
  } catch (e) { toast(e.message, 'err') } finally { busy.value = false; showReject.value = false }
}

const resolvedClass = (v) => (v?.includes('解决') && !v.includes('未') ? 'badge-green' : v ? 'badge-gray' : '')
</script>

<template>
  <section class="card ccard" v-if="cases?.length">
    <header class="ccard-head">
      <div class="ccard-title">
        <Icon name="archive" :size="16" />
        <h3>类案参考</h3>
        <span class="badge badge-green">历史工单经验</span>
      </div>
      <span class="ccard-note">来自本地历史工单库 · 已脱敏 · 仅供借鉴</span>
    </header>

    <div class="ccard-body">
      <article v-for="c in cases" :key="c.n" :id="'case-' + c.n" class="case-item">
        <div class="case-row" @click="open[c.n] = !open[c.n]">
          <span class="case-num">{{ c.n }}</span>
          <div class="case-main">
            <p class="case-complaint" :class="{ clamp: !open[c.n] }">{{ c.complaint }}</p>
            <div class="case-meta">
              <span class="badge badge-blue">匹配 {{ Math.round(c.match * 100) }}%</span>
              <span v-if="c.category" class="case-cat">{{ c.category }}</span>
              <span v-if="c.location" class="case-cat">{{ c.location }}</span>
              <span v-if="c.entry_date" class="case-cat">{{ c.entry_date }}</span>
              <span v-if="c.is_resolved" class="badge" :class="resolvedClass(c.is_resolved)">{{ c.is_resolved }}</span>
              <span v-if="c.is_satisfied" class="badge" :class="resolvedClass(c.is_satisfied)">{{ c.is_satisfied }}</span>
            </div>
          </div>
          <Icon name="chevron" :size="15" class="case-chev" :style="open[c.n] ? 'transform:rotate(180deg)' : ''" />
        </div>
        <div v-if="open[c.n]" class="case-handling">
          <div class="case-handling-label">当年办理情况</div>
          <p>{{ c.handling || '未记录办理情况' }}</p>
        </div>
      </article>

      <!-- 经验提炼 -->
      <div class="exp">
        <template v-if="expState === 'idle' && !readonly">
          <button class="btn btn-ghost" @click="extract"><Icon name="sparkle" :size="14" />提炼办理经验</button>
          <span class="exp-hint">基于上述类案由 AI 提炼常见处理路径与注意点</span>
        </template>
        <template v-else-if="expState !== 'idle'">
          <div class="exp-head">
            <Icon name="sparkle" :size="14" />
            <b>办理经验提炼</b>
            <span class="exp-tag">历史做法不代表现行政策，请以现行政策核实为准</span>
          </div>
          <div v-if="expState === 'error'" class="exp-error">{{ expError }} <button class="btn btn-plain btn-sm" @click="extract">重试</button></div>
          <CitedText v-else :text="expText" :streaming="expState === 'streaming'" @cite="(c) => flashCase(c.n)" />
          <div v-if="expState === 'done' && !readonly" class="exp-foot">
            <template v-if="!experienceDecision">
              <button class="btn btn-sm adopt" :disabled="busy" @click="decide('adopt')"><Icon name="check" :size="13" />有帮助，采纳</button>
              <button class="btn btn-sm reject" :disabled="busy" @click="showReject = true"><Icon name="x" :size="13" />没帮助</button>
            </template>
            <span v-else class="exp-decided" :class="experienceDecision.decision === 'adopt' ? 'ok' : 'no'">
              <Icon :name="experienceDecision.decision === 'adopt' ? 'check' : 'x'" :size="13" />
              {{ experienceDecision.decision === 'adopt' ? '已采纳' : '已标记为无帮助' }}
            </span>
          </div>
          <div v-else-if="experienceDecision && readonly" class="exp-foot">
            <span class="exp-decided" :class="experienceDecision.decision === 'adopt' ? 'ok' : 'no'">
              {{ experienceDecision.decision === 'adopt' ? '已采纳' : '已标记为无帮助' }}
            </span>
          </div>
        </template>
      </div>
    </div>

    <Modal v-if="showReject" title="反馈：经验提炼没帮助" @close="showReject = false">
      <select class="select" v-model="rejectReason">
        <option>与本案情形不符</option>
        <option>提炼内容太空泛</option>
        <option>类案本身不相似</option>
        <option>其他</option>
      </select>
      <template #footer>
        <button class="btn btn-plain" @click="showReject = false">取消</button>
        <button class="btn btn-danger" :disabled="busy" @click="decide('reject', { reason: rejectReason })">提交</button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.ccard-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--line); flex-wrap: wrap; gap: 6px; }
.ccard-title { display: flex; align-items: center; gap: 8px; color: var(--green); }
.ccard-title h3 { font-size: 15px; font-family: var(--font-serif); color: var(--ink); }
.ccard-note { font-size: 12px; color: var(--ink-3); }
.ccard-body { padding: 4px 18px 16px; }
.case-item { border-bottom: 1px solid var(--line); }
.case-item:last-of-type { border-bottom: none; }
.case-row { display: flex; gap: 12px; padding: 12px 0; cursor: pointer; align-items: flex-start; }
.case-num {
  flex: none; width: 22px; height: 22px; border-radius: 6px; margin-top: 1px;
  background: var(--green-soft); color: var(--green); font-size: 12px; font-weight: 600;
  display: grid; place-items: center; border: 1px solid #cbe2d5;
}
.case-main { flex: 1; min-width: 0; }
.case-complaint { font-size: 13.5px; color: var(--ink); }
.case-complaint.clamp { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.case-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; align-items: center; }
.case-cat { font-size: 12px; color: var(--ink-3); }
.case-chev { color: var(--ink-3); margin-top: 4px; flex: none; transition: transform .15s; }
.case-handling { margin: 0 0 12px 34px; background: #f9f8f4; border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; font-size: 13px; color: var(--ink-2); }
.case-handling-label { font-size: 11.5px; color: var(--ink-3); margin-bottom: 4px; font-weight: 500; }
.exp { margin-top: 12px; padding: 12px 14px; background: linear-gradient(180deg, #f6faf7, #fbfdfb); border: 1px solid #d9e9de; border-radius: 10px; }
.exp-hint { font-size: 12px; color: var(--ink-3); margin-left: 10px; }
.exp-head { display: flex; align-items: center; gap: 6px; color: var(--green); margin-bottom: 8px; flex-wrap: wrap; }
.exp-head b { color: var(--ink); font-size: 13.5px; }
.exp-tag { font-size: 11.5px; color: var(--amber); background: var(--amber-soft); padding: 2px 8px; border-radius: 999px; }
.exp-error { color: var(--red); font-size: 13px; display: flex; align-items: center; gap: 10px; }
.exp-foot { margin-top: 10px; display: flex; gap: 8px; align-items: center; }
.exp-decided { font-size: 13px; display: inline-flex; gap: 5px; align-items: center; }
.exp-decided.ok { color: var(--green); }
.exp-decided.no { color: var(--ink-3); }
.btn.adopt { background: var(--green-soft); color: var(--green); border-color: #cbe2d5; }
.btn.adopt:hover { background: var(--green); color: #fff; }
.btn.reject { background: #fff; color: var(--ink-3); border-color: var(--line-strong); }
</style>
