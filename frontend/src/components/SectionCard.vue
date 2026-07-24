<script setup>
import { computed, ref } from 'vue'
import Icon from './Icon.vue'
import CitedText from './CitedText.vue'
import Modal from './Modal.vue'
import { api } from '../api'
import { toast } from '../toast'
import { copyToClipboard } from '../clipboard'

const props = defineProps({
  name: String,             // interpret | reply | method
  consultId: Number,
  text: { type: String, default: '' },
  state: { type: String, default: 'idle' },   // idle | streaming | done
  decision: Object,         // {decision, modified_text, reason, created_at} | null
  readonly: Boolean,
})
const emit = defineEmits(['cite', 'decided'])

const META = {
  interpret: { title: '条款解释', icon: 'book', hint: '政策对本诉求意味着什么' },
  reply: { title: '回复话术', icon: 'message', hint: '参考话术，请调整后使用' },
  method: { title: '办理方法', icon: 'route', hint: '流程 · 材料 · 渠道 · 时限' },
}
const meta = computed(() => META[props.name] || { title: props.name, icon: 'file', hint: '' })

const busy = ref(false)
const showModify = ref(false)
const showReject = ref(false)
const modifyText = ref('')
const rejectReason = ref('内容不准确')
const showModified = ref(false)

async function decide(decision, extra = {}) {
  busy.value = true
  try {
    await api.post(`/api/consults/${props.consultId}/decisions`, { section: props.name, decision, ...extra })
    emit('decided', { section: props.name, decision, ...extra })
    toast({ adopt: '已记录：采纳', modify: '已记录：修改后采纳', reject: '已记录：拒绝' }[decision], 'ok')
  } catch (e) { toast(e.message, 'err') } finally {
    busy.value = false
    showModify.value = false
    showReject.value = false
  }
}

async function copyText() {
  const t = (props.decision?.modified_text || props.text).replace(/[\[【〔](材料|案例)\s*\d+[\]】〕]/g, '')
  const ok = await copyToClipboard(t)
  toast(ok ? '已复制（角标已清除），请人工核实后使用' : '复制失败，请手动选择文本复制', ok ? 'ok' : 'warn')
}

const decisionLabel = { adopt: '已采纳', modify: '已修改采纳', reject: '已拒绝' }
</script>

<template>
  <section class="card scard" v-show="state !== 'idle' || text || decision">
    <header class="scard-head">
      <div class="scard-title">
        <Icon :name="meta.icon" :size="15" />
        <h3>{{ meta.title }}</h3>
        <span class="scard-hint">{{ meta.hint }}</span>
      </div>
      <button v-if="name === 'reply' && text && state === 'done'" class="btn btn-plain btn-sm" @click="copyText">
        <Icon name="copy" :size="13" />复制
      </button>
    </header>

    <div class="scard-body">
      <CitedText :text="text" :streaming="state === 'streaming'" @cite="(c) => emit('cite', c)" />
      <div v-if="state === 'streaming' && !text" class="s-waiting">
        <div class="skeleton" style="width: 90%; height: 13px" />
        <div class="skeleton" style="width: 72%; height: 13px; margin-top: 8px" />
      </div>
    </div>

    <footer v-if="state === 'done' && !readonly" class="scard-foot">
      <template v-if="!decision">
        <span class="foot-ask">该部分是否可用？</span>
        <div class="foot-btns">
          <button class="btn btn-sm adopt" :disabled="busy" @click="decide('adopt')"><Icon name="check" :size="13" />采纳</button>
          <button class="btn btn-sm modify" :disabled="busy" @click="modifyText = text; showModify = true"><Icon name="edit" :size="13" />修改后采纳</button>
          <button class="btn btn-sm reject" :disabled="busy" @click="showReject = true"><Icon name="x" :size="13" />拒绝</button>
        </div>
      </template>
      <template v-else>
        <span class="decided" :class="'d-' + decision.decision">
          <Icon :name="decision.decision === 'reject' ? 'x' : 'check'" :size="13" />
          {{ decisionLabel[decision.decision] }}
          <em v-if="decision.reason">（{{ decision.reason }}）</em>
        </span>
        <div class="foot-btns">
          <button v-if="decision.decision === 'modify'" class="btn btn-plain btn-sm" @click="showModified = true">查看修改稿</button>
          <button class="btn btn-plain btn-sm" @click="emit('decided', { section: name, decision: null }); ">重新决策</button>
        </div>
      </template>
    </footer>
    <footer v-else-if="decision && readonly" class="scard-foot">
      <span class="decided" :class="'d-' + decision.decision">
        <Icon :name="decision.decision === 'reject' ? 'x' : 'check'" :size="13" />
        {{ decisionLabel[decision.decision] }}<em v-if="decision.reason">（{{ decision.reason }}）</em>
        <em class="d-time">{{ decision.created_at }}</em>
      </span>
      <button v-if="decision.decision === 'modify'" class="btn btn-plain btn-sm" @click="showModified = true">查看修改稿</button>
    </footer>

    <Modal v-if="showModify" title="修改后采纳" width="620px" @close="showModify = false">
      <p class="modal-tip">在生成内容基础上修改为实际可用的版本，修改稿将随工单留痕。</p>
      <textarea class="textarea" v-model="modifyText" rows="9" />
      <template #footer>
        <button class="btn btn-plain" @click="showModify = false">取消</button>
        <button class="btn btn-primary" :disabled="busy || !modifyText.trim()" @click="decide('modify', { modified_text: modifyText })">保存并采纳</button>
      </template>
    </Modal>

    <Modal v-if="showReject" title="拒绝该部分" @close="showReject = false">
      <p class="modal-tip">拒绝原因将用于改进生成质量（不影响你的使用）。</p>
      <select class="select" v-model="rejectReason">
        <option>内容不准确</option>
        <option>与诉求不相关</option>
        <option>存在合规风险</option>
        <option>其他</option>
      </select>
      <template #footer>
        <button class="btn btn-plain" @click="showReject = false">取消</button>
        <button class="btn btn-danger" :disabled="busy" @click="decide('reject', { reason: rejectReason })">确认拒绝</button>
      </template>
    </Modal>

    <Modal v-if="showModified" title="修改稿" width="620px" @close="showModified = false">
      <div class="modified-view">{{ decision?.modified_text }}</div>
      <template #footer>
        <button class="btn btn-primary" @click="showModified = false">关闭</button>
      </template>
    </Modal>
  </section>
</template>

<style scoped>
.scard-head { display: flex; align-items: center; justify-content: space-between; padding: 13px 18px 0; }
.scard-title { display: flex; align-items: baseline; gap: 8px; color: var(--primary); }
.scard-title h3 { font-size: 15px; font-family: var(--font-serif); color: var(--ink); }
.scard-title svg { align-self: center; }
.scard-hint { font-size: 12px; color: var(--ink-3); }
.scard-body { padding: 10px 18px 14px; font-size: 14px; color: var(--ink); }
.s-waiting { padding: 4px 0 8px; }
.scard-foot {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 10px 18px; border-top: 1px solid var(--line); background: #fcfbf8;
  border-radius: 0 0 var(--radius) var(--radius); flex-wrap: wrap;
}
.foot-ask { font-size: 12.5px; color: var(--ink-3); }
.foot-btns { display: flex; gap: 8px; }
.btn.adopt { background: var(--green-soft); color: var(--green); border-color: #cbe2d5; }
.btn.adopt:hover { background: var(--green); color: #fff; }
.btn.modify { background: var(--primary-soft); color: var(--primary); border-color: var(--primary-line); }
.btn.modify:hover { background: var(--primary); color: #fff; }
.btn.reject { background: #fff; color: var(--ink-3); border-color: var(--line-strong); }
.btn.reject:hover { background: var(--red-soft); color: var(--red); border-color: #e5c5c5; }
.decided { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500; }
.decided em { font-style: normal; color: var(--ink-3); font-weight: 400; }
.d-adopt { color: var(--green); }
.d-modify { color: var(--primary); }
.d-reject { color: var(--ink-3); }
.d-time { font-size: 12px; }
.modal-tip { font-size: 12.5px; color: var(--ink-3); margin-bottom: 10px; }
.modified-view { white-space: pre-wrap; background: var(--bg); border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; max-height: 50vh; overflow: auto; }
</style>
