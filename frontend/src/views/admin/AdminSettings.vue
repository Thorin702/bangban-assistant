<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api'
import { toast } from '../../toast'
import { store } from '../../store'
import Toggle from '../../components/Toggle.vue'
import Icon from '../../components/Icon.vue'
import Modal from '../../components/Modal.vue'

const s = ref(null)
const runtime = ref(null)
const llmMeta = ref({ api_key_set: false, api_key_hint: '' })
const llmApiKey = ref('')
const busy = ref(false)
const caseOn = ref(false)
const testing = ref(false)
const testResult = ref(null)
const showJson = ref(false)
const jsonText = ref('')
const jsonError = ref('')

const cityOptions = ref([])  // 全国地市预置库（后端返回），用于输入联想

onMounted(load)
async function load() {
  const data = await api.get('/api/admin/settings')
  s.value = data.settings
  runtime.value = data.runtime
  llmMeta.value = data.llm
  caseOn.value = data.settings.case_feature_enabled === '1'
  if (!cityOptions.value.length) {
    try { cityOptions.value = (await api.get('/api/admin/cities')).cities } catch { /* 忽略 */ }
  }
}

async function save() {
  if (!s.value.default_service_area) return toast('请先选择办理地域（必填）', 'warn')
  try { JSON.parse(s.value.gen_extra_params || '{}') } catch { return toast('扩展参数不是合法 JSON 对象', 'err') }
  busy.value = true
  try {
    const body = { settings: { ...s.value, case_feature_enabled: caseOn.value ? '1' : '0' } }
    if (llmApiKey.value.trim()) body.llm_api_key = llmApiKey.value.trim()
    await api.put('/api/admin/settings', body)
    llmApiKey.value = ''
    toast('已保存，立即生效', 'ok')
    await load()
    store.config = await api.get('/api/config')
  } catch (e) { toast(e.message, 'err') } finally { busy.value = false }
}

async function toggleCase(v) {
  caseOn.value = v
  try {
    await api.put('/api/admin/settings', { settings: { case_feature_enabled: v ? '1' : '0' } })
    store.config = await api.get('/api/config')
    toast(v ? '类案经验已开启（M2）' : '类案经验已关闭（回到纯政策参考）', 'ok')
  } catch (e) { caseOn.value = !v; toast(e.message, 'err') }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await api.post('/api/admin/llm/test', {
      base_url: s.value.llm_base_url, model: s.value.llm_model, api_key: llmApiKey.value.trim(),
    })
  } catch (e) { testResult.value = { ok: false, message: e.message } } finally { testing.value = false }
}

function openJson() {
  let extra = {}
  try { extra = JSON.parse(s.value.gen_extra_params || '{}') } catch { extra = {} }
  jsonText.value = JSON.stringify({
    llm_base_url: s.value.llm_base_url,
    llm_model: s.value.llm_model,
    gen_temperature: Number(s.value.gen_temperature),
    gen_top_p: Number(s.value.gen_top_p),
    gen_max_tokens: Number(s.value.gen_max_tokens),
    gen_enable_thinking: s.value.gen_enable_thinking === '1',
    gen_extra_params: extra,
    consult_system_prompt: s.value.consult_system_prompt,
    experience_system_prompt: s.value.experience_system_prompt,
  }, null, 2)
  jsonError.value = ''
  showJson.value = true
}

function applyJson() {
  let o
  try { o = JSON.parse(jsonText.value) } catch (e) { jsonError.value = 'JSON 解析失败：' + e.message; return }
  const set = (k, v) => { if (v !== undefined) s.value[k] = v }
  set('llm_base_url', o.llm_base_url != null ? String(o.llm_base_url) : undefined)
  set('llm_model', o.llm_model != null ? String(o.llm_model) : undefined)
  set('gen_temperature', o.gen_temperature != null ? String(o.gen_temperature) : undefined)
  set('gen_top_p', o.gen_top_p != null ? String(o.gen_top_p) : undefined)
  set('gen_max_tokens', o.gen_max_tokens != null ? String(o.gen_max_tokens) : undefined)
  if (o.gen_enable_thinking !== undefined) s.value.gen_enable_thinking = o.gen_enable_thinking ? '1' : '0'
  if (o.gen_extra_params !== undefined) s.value.gen_extra_params = JSON.stringify(o.gen_extra_params || {})
  set('consult_system_prompt', o.consult_system_prompt != null ? String(o.consult_system_prompt) : undefined)
  set('experience_system_prompt', o.experience_system_prompt != null ? String(o.experience_system_prompt) : undefined)
  showJson.value = false
  toast('已载入 JSON，请点击「保存全部参数」生效', 'ok')
}
</script>

<template>
  <div class="st" v-if="s">
    <!-- 类案经验开关 -->
    <div class="card feature-card" :class="{ on: caseOn }">
      <div class="feature-main">
        <div class="feature-title">
          <Icon name="archive" :size="18" />
          <div>
            <h3>类案经验（M2 · 真实历史数据）</h3>
            <p>开启后咨询页展示相似历史工单与经验提炼；关闭即回到纯政策参考。<b>随时切换，立即生效</b>，可按演示对象控制展示范围。</p>
          </div>
        </div>
        <Toggle :model-value="caseOn" @update:model-value="toggleCase" />
      </div>
      <div class="feature-stats" v-if="runtime?.cases">
        <template v-if="runtime.cases.available">
          <span class="fstat"><b>{{ runtime.cases.count.toLocaleString() }}</b> 条历史工单已接入</span>
          <span class="fstat">时间范围 <b>{{ runtime.cases.date_range?.[0] }} ~ {{ runtime.cases.date_range?.[1] }}</b></span>
          <span class="fstat">已做展示级脱敏 · 数据仅限内部测试评估使用</span>
        </template>
        <span v-else class="fstat warn">历史工单库未构建（运行 scripts/ingest_cases.py 后可用）</span>
      </div>
      <div class="feature-params" v-if="caseOn">
        <label>类案返回条数</label>
        <input class="input" style="width: 90px" v-model="s.case_top_k" />
        <span class="fp-sep">|</span>
        <label>办件研判（时限 / 满意度处方 / 关联预警）</label>
        <Toggle :model-value="s.research_enabled === '1'" @update:model-value="(v) => s.research_enabled = v ? '1' : '0'" />
      </div>
    </div>

    <!-- 生成模型接入 -->
    <div class="card panel">
      <div class="panel-h">
        <h3>生成模型接入</h3>
        <span class="badge" :class="runtime?.llm_ready ? 'badge-green' : 'badge-amber'">
          {{ runtime?.llm_ready ? '已就绪' : '未配置' }}
        </span>
      </div>
      <p class="panel-desc">填写 OpenAI 兼容接口的调用地址、API Key 与模型型号（如阿里云百炼 qwen3-32b），保存前建议先测试连接。</p>
      <div class="llm-grid">
        <div class="llm-full">
          <label class="field-label">调用地址（base_url）</label>
          <input class="input mono" v-model="s.llm_base_url" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
        </div>
        <div>
          <label class="field-label">模型型号</label>
          <input class="input mono" v-model="s.llm_model" placeholder="qwen3-32b" />
        </div>
        <div>
          <label class="field-label">
            API Key
            <span v-if="llmMeta.api_key_set" class="key-hint">当前：{{ llmMeta.api_key_hint }}</span>
          </label>
          <input class="input mono" type="password" v-model="llmApiKey"
                 :placeholder="llmMeta.api_key_set ? '已配置，如需更换请输入新 Key' : '请输入 API Key'" autocomplete="off" />
        </div>
      </div>
      <div class="llm-actions">
        <button class="btn btn-ghost" :disabled="testing" @click="testConnection">
          <Icon name="refresh" :size="14" :class="{ spinning: testing }" />{{ testing ? '测试中…' : '测试连接' }}
        </button>
        <span v-if="testResult" class="test-result" :class="testResult.ok ? 'ok' : 'fail'">
          <Icon :name="testResult.ok ? 'check' : 'x'" :size="14" />
          {{ testResult.message }}<em v-if="testResult.latency_ms"> · {{ testResult.latency_ms }}ms</em>
        </span>
      </div>
    </div>

    <!-- 生成参数 -->
    <div class="card panel">
      <div class="panel-h">
        <h3>生成参数</h3>
        <button class="btn btn-plain btn-sm" @click="openJson"><Icon name="file" :size="13" />JSON 编辑</button>
      </div>
      <p class="panel-desc">按承办单位的答复口径与生成稳定性需要调节；温度越低越忠实材料，越高越灵活。</p>
      <div class="grid-4">
        <div><label class="field-label">温度 temperature</label><input class="input" v-model="s.gen_temperature" /></div>
        <div><label class="field-label">top_p</label><input class="input" v-model="s.gen_top_p" /></div>
        <div><label class="field-label">最大生成长度 max_tokens</label><input class="input" v-model="s.gen_max_tokens" /></div>
        <div class="thinking-cell">
          <label class="field-label">思维链 enable_thinking</label>
          <div class="thinking-row">
            <Toggle :model-value="s.gen_enable_thinking === '1'" @update:model-value="(v) => s.gen_enable_thinking = v ? '1' : '0'" />
            <span class="thinking-note">仅 DashScope 流式生效，开启会增加延迟</span>
          </div>
        </div>
      </div>
      <div style="margin-top: 12px">
        <label class="field-label">扩展参数（JSON，透传至接口，如 {"presence_penalty": 0.2, "frequency_penalty": 0.1}）</label>
        <textarea class="textarea mono" rows="2" v-model="s.gen_extra_params" />
      </div>
    </div>

    <!-- 提示词 -->
    <div class="card panel">
      <h3>提示词 · 答复口径</h3>
      <p class="panel-desc">
        不同承办单位口径不同，可在此直接编辑系统提示词以调节生成风格与规则。
        <b>请保留三段标记</b>【条款解释】【回复话术】【办理方法】，否则分段展示会失效。
      </p>
      <label class="field-label">咨询生成 · 系统提示词</label>
      <textarea class="textarea prompt-area" rows="12" v-model="s.consult_system_prompt" />
      <label class="field-label" style="margin-top: 14px">类案经验提炼 · 系统提示词</label>
      <textarea class="textarea prompt-area" rows="8" v-model="s.experience_system_prompt" />
    </div>

    <!-- 地域与时间 -->
    <div class="card panel">
      <h3>适用地域与生效时间 <span class="panel-note">逐地市部署，由后台设定，一线无需选择</span></h3>
      <div class="grid-2">
        <div>
          <label class="field-label">办理地域 <em class="req">必填 · 地市级</em></label>
          <input class="input" list="bb-city-list" v-model.trim="s.default_service_area"
                 :class="{ 'field-error': !s.default_service_area }"
                 placeholder="输入地市名，如 枣庄 / 临沂 / 呼伦贝尔" autocomplete="off" />
          <datalist id="bb-city-list">
            <option v-for="c in cityOptions" :key="c" :value="c" />
          </datalist>
          <p class="area-hint">
            须为全国地市级（预置 {{ cityOptions.length }} 个：地级市 / 自治州 / 地区 / 直辖市）。
            保存时与预置库比对，非法名称将被拒绝；系统据此严格限定检索与生成，其他地市材料自动过滤。
          </p>
        </div>
        <div>
          <label class="field-label">政策生效时间（留空为当前）</label>
          <input class="input" v-model="s.default_eff_time" placeholder="如 2024年 / 留空" />
        </div>
      </div>
    </div>

    <!-- 检索与权威源 -->
    <div class="card panel">
      <h3>政策检索与权威源</h3>
      <div class="grid-3">
        <div><label class="field-label">进入 prompt 的材料数（Top-N）</label><input class="input" v-model="s.top_n" /></div>
        <div><label class="field-label">每材料段落上限</label><input class="input" v-model="s.segment_count" /></div>
        <div><label class="field-label">页面免责声明</label><input class="input" v-model="s.disclaimer_text" /></div>
      </div>
      <div class="grid-3" style="margin-top: 12px">
        <div>
          <label class="field-label">权威域名（每行一个，后缀匹配）</label>
          <textarea class="textarea" rows="4" v-model="s.authoritative_domains" />
        </div>
        <div>
          <label class="field-label">权威机构名关键词（每行一个）</label>
          <textarea class="textarea" rows="4" v-model="s.authoritative_source_names" />
        </div>
        <div>
          <label class="field-label">屏蔽源关键词（每行一个）</label>
          <textarea class="textarea" rows="4" v-model="s.blocked_source_keywords" />
        </div>
      </div>
    </div>

    <!-- 运行环境 -->
    <div class="card panel" v-if="runtime">
      <h3>运行环境</h3>
      <div class="rt-item">
        <span class="rt-label">政策检索</span>
        <span class="badge" :class="runtime.retrieval_mode === 'live' ? 'badge-green' : 'badge-amber'">
          {{ runtime.retrieval_mode === 'live' ? '真实接口（dknowc）' : '演示模式（未配置密钥）' }}
        </span>
        <code class="rt-code">{{ runtime.retrieval_endpoint }}</code>
      </div>
      <p class="rt-tip">政策检索走 dknowc 可信搜索，密钥在 backend/.env 的 <code>DKNOWC_API_KEY</code> 配置后自动切换真实检索。</p>
    </div>

    <div class="save-bar">
      <button class="btn btn-primary" :disabled="busy" @click="save"><Icon name="check" :size="14" />{{ busy ? '保存中…' : '保存全部参数' }}</button>
      <span class="save-note">保存后对新发起的咨询立即生效</span>
    </div>

    <Modal v-if="showJson" title="以 JSON 编辑生成配置" width="720px" @close="showJson = false">
      <p class="json-tip">直接编辑生成模型、参数与提示词。应用后需再点「保存全部参数」写入。（API Key 不含在此，单独在上方填写）</p>
      <textarea class="textarea mono json-area" rows="18" v-model="jsonText" spellcheck="false" />
      <p v-if="jsonError" class="json-err">{{ jsonError }}</p>
      <template #footer>
        <button class="btn btn-plain" @click="showJson = false">取消</button>
        <button class="btn btn-primary" @click="applyJson">应用到表单</button>
      </template>
    </Modal>
  </div>
</template>

<style scoped>
.st { display: flex; flex-direction: column; gap: 16px; }
.mono { font-family: var(--font-mono); font-size: 12.5px; }
.panel { padding: 18px 20px; }
.panel h3 { font-size: 14.5px; font-family: var(--font-serif); }
.panel-h { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 4px; }
.panel-desc { font-size: 12.5px; color: var(--ink-3); margin: 6px 0 14px; }
.panel-desc b { color: var(--amber); }
.panel-note { font-size: 11.5px; color: var(--ink-3); font-weight: 400; font-family: var(--font-sans); margin-left: 8px; }

.feature-card { padding: 18px 20px; border-left: 3px solid var(--line-strong); transition: border-color .2s; }
.feature-card.on { border-left-color: var(--green); }
.feature-main { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.feature-title { display: flex; gap: 12px; color: var(--green); }
.feature-title h3 { font-size: 15.5px; font-family: var(--font-serif); color: var(--ink); }
.feature-title p { font-size: 13px; color: var(--ink-2); margin-top: 6px; max-width: 640px; }
.feature-title b { color: var(--green); }
.feature-stats { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--line); }
.fstat { font-size: 12.5px; color: var(--ink-3); }
.fstat b { color: var(--ink); font-family: var(--font-serif); }
.fstat.warn { color: var(--amber); }
.feature-params { display: flex; align-items: center; gap: 10px; margin-top: 12px; font-size: 13px; color: var(--ink-2); flex-wrap: wrap; }
.fp-sep { color: var(--line-strong); }

.llm-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.llm-full { grid-column: 1 / -1; }
.key-hint { font-weight: 400; color: var(--ink-3); font-family: var(--font-mono); font-size: 11px; margin-left: 6px; }
.llm-actions { display: flex; align-items: center; gap: 14px; margin-top: 14px; flex-wrap: wrap; }
.test-result { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
.test-result.ok { color: var(--green); }
.test-result.fail { color: var(--red); }
.test-result em { font-style: normal; color: var(--ink-3); }
.spinning { animation: rot .8s linear infinite; }
@keyframes rot { to { transform: rotate(360deg); } }

.grid-4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.req { font-style: normal; color: var(--accent); font-size: 11px; margin-left: 4px; }
.field-error { border-color: var(--accent); }
.area-hint { font-size: 11.5px; color: var(--ink-3); margin-top: 6px; }
.thinking-cell { min-width: 200px; }
.thinking-row { display: flex; align-items: center; gap: 10px; }
.thinking-note { font-size: 11.5px; color: var(--ink-3); }
.prompt-area { font-size: 13px; line-height: 1.7; }

.rt-item { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.rt-label { font-size: 13px; color: var(--ink-2); width: 64px; flex: none; }
.rt-code { font-family: var(--font-mono); font-size: 11.5px; color: var(--ink-3); background: var(--bg); padding: 2px 8px; border-radius: 5px; }
.rt-tip { font-size: 12px; color: var(--ink-3); margin-top: 12px; }
.rt-tip code { font-family: var(--font-mono); background: var(--bg); padding: 1px 5px; border-radius: 4px; }

.save-bar { display: flex; align-items: center; gap: 14px; position: sticky; bottom: 16px; background: rgba(255,255,255,.92); backdrop-filter: blur(8px); border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px; box-shadow: var(--shadow-card); }
.save-note { font-size: 12.5px; color: var(--ink-3); }

.json-tip { font-size: 12.5px; color: var(--ink-3); margin-bottom: 10px; }
.json-area { font-size: 12.5px; line-height: 1.6; }
.json-err { color: var(--red); font-size: 12.5px; margin-top: 8px; }
@media (max-width: 720px) { .llm-grid, .grid-2 { grid-template-columns: 1fr; } }
</style>
