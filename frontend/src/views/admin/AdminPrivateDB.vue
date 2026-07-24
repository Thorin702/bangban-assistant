<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api'
import { toast } from '../../toast'
import { store } from '../../store'
import Icon from '../../components/Icon.vue'
import Toggle from '../../components/Toggle.vue'

const data = ref({ stats: { doc_count: 0, segment_count: 0 }, docs: [] })
const enabled = ref(false)
const busy = ref(false)
const form = ref({ title: '', doc_no: '', date: '', source: '', region: '', content: '' })
const fileInput = ref(null)

onMounted(load)
async function load() {
  data.value = await api.get('/api/admin/private-docs')
  const s = await api.get('/api/admin/settings')
  enabled.value = s.settings.private_db_enabled === '1'
}

async function toggle(v) {
  enabled.value = v
  try {
    await api.put('/api/admin/settings', { settings: { private_db_enabled: v ? '1' : '0' } })
    store.config = await api.get('/api/config')
    toast(v ? '私有政策库已启用，将参与检索' : '私有政策库已停用', 'ok')
  } catch (e) { enabled.value = !v; toast(e.message, 'err') }
}

function pickFile() { fileInput.value?.click() }
function onFile(e) {
  const f = e.target.files?.[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => {
    form.value.content = String(reader.result || '')
    if (!form.value.title) form.value.title = f.name.replace(/\.(txt|md|markdown)$/i, '')
    toast('已读入文件内容，可编辑后导入', 'ok')
  }
  reader.readAsText(f)
  e.target.value = ''
}

async function submit() {
  if (!form.value.title.trim() || form.value.content.trim().length < 10) return toast('请填写标题与正文（正文≥10字）', 'warn')
  busy.value = true
  try {
    const r = await api.post('/api/admin/private-docs', form.value)
    toast(`已导入并治理为 ${r.seg_count} 个可检索段落`, 'ok')
    form.value = { title: '', doc_no: '', date: '', source: '', region: '', content: '' }
    load()
  } catch (e) { toast(e.message, 'err') } finally { busy.value = false }
}

async function del(doc) {
  if (!confirm(`确认删除《${doc.title}》？`)) return
  try { await api.delete(`/api/admin/private-docs/${doc.id}`); toast('已删除', 'ok'); load() }
  catch (e) { toast(e.message, 'err') }
}
</script>

<template>
  <div class="pv">
    <div class="card feature-card" :class="{ on: enabled }">
      <div class="feature-main">
        <div class="feature-title">
          <Icon name="shield" :size="18" />
          <div>
            <h3>私有政策库（可选）</h3>
            <p>导入本地市/区不公开的政策、法规、办事细则，平台自动治理分段并建立检索。启用后，本地政策将<b>与深知检索结果一并参与</b>，且本地政策优先展示。</p>
          </div>
        </div>
        <Toggle :model-value="enabled" @update:model-value="toggle" />
      </div>
      <div class="feature-stats">
        <span class="fstat">已收录 <b>{{ data.stats.doc_count }}</b> 份文档</span>
        <span class="fstat"><b>{{ data.stats.segment_count }}</b> 个可检索段落</span>
        <span class="fstat">数据仅存于本地，不外发</span>
      </div>
    </div>

    <div class="card panel">
      <h3>导入政策文档</h3>
      <p class="panel-desc">粘贴正文，或从 .txt / .md 文件读入；治理后按段落检索，可被引用溯源。</p>
      <div class="imp-grid">
        <div class="imp-full">
          <label class="field-label">标题 <em>必填</em></label>
          <input class="input" v-model="form.title" placeholder="如：滕州市老旧小区改造供暖接入补贴实施细则（试行）" />
        </div>
        <div><label class="field-label">发文字号</label><input class="input" v-model="form.doc_no" placeholder="如 滕住建〔2025〕33号" /></div>
        <div><label class="field-label">发布日期</label><input class="input" v-model="form.date" placeholder="如 2025-03-01" /></div>
        <div><label class="field-label">来源机构</label><input class="input" v-model="form.source" placeholder="如 滕州市住房和城乡建设局" /></div>
        <div><label class="field-label">适用地域</label><input class="input" v-model="form.region" placeholder="如 滕州" /></div>
      </div>
      <div class="imp-content">
        <div class="imp-content-head">
          <label class="field-label">正文 <em>必填</em></label>
          <button class="btn btn-plain btn-sm" @click="pickFile"><Icon name="file" :size="13" />从文件读入</button>
          <input ref="fileInput" type="file" accept=".txt,.md,.markdown" style="display:none" @change="onFile" />
        </div>
        <textarea class="textarea" rows="9" v-model="form.content" placeholder="粘贴政策原文。建议保留“第X条 / 一、二、三、”等条款结构，平台会据此更好地分段。" />
      </div>
      <div class="imp-actions">
        <button class="btn btn-primary" :disabled="busy" @click="submit"><Icon name="plus" :size="14" />{{ busy ? '导入中…' : '导入并治理' }}</button>
      </div>
    </div>

    <div class="card panel">
      <h3>已收录文档 <span class="panel-note">共 {{ data.docs.length }} 份</span></h3>
      <table v-if="data.docs.length" class="table">
        <thead><tr><th>标题</th><th>发文字号</th><th>地域</th><th>段落</th><th>导入时间</th><th style="width:70px"></th></tr></thead>
        <tbody>
          <tr v-for="d in data.docs" :key="d.id">
            <td>{{ d.title }}<div class="dim">{{ d.source }}</div></td>
            <td>{{ d.doc_no || '—' }}</td>
            <td>{{ d.region || '—' }}</td>
            <td>{{ d.seg_count }}</td>
            <td class="dim">{{ d.created_at }}</td>
            <td><button class="btn btn-danger btn-sm" @click="del(d)">删除</button></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty-hint">尚未导入任何文档。导入本地政策后，启用上方开关即可参与检索。</p>
    </div>
  </div>
</template>

<style scoped>
.pv { display: flex; flex-direction: column; gap: 16px; }
.feature-card { padding: 18px 20px; border-left: 3px solid var(--line-strong); transition: border-color .2s; }
.feature-card.on { border-left-color: var(--green); }
.feature-main { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.feature-title { display: flex; gap: 12px; color: var(--green); }
.feature-title h3 { font-size: 15.5px; font-family: var(--font-serif); color: var(--ink); }
.feature-title p { font-size: 13px; color: var(--ink-2); margin-top: 6px; max-width: 660px; }
.feature-title b { color: var(--green); }
.feature-stats { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--line); }
.fstat { font-size: 12.5px; color: var(--ink-3); }
.fstat b { color: var(--ink); font-family: var(--font-serif); }
.panel { padding: 18px 20px; }
.panel h3 { font-size: 14.5px; font-family: var(--font-serif); }
.panel-desc { font-size: 12.5px; color: var(--ink-3); margin: 6px 0 14px; }
.panel-note { font-size: 11.5px; color: var(--ink-3); font-weight: 400; font-family: var(--font-sans); margin-left: 8px; }
.imp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.imp-full { grid-column: 1 / -1; }
.field-label em { font-style: normal; color: var(--accent); font-size: 11px; margin-left: 4px; }
.imp-content { margin-top: 12px; }
.imp-content-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.imp-content-head .field-label { margin-bottom: 0; }
.imp-actions { margin-top: 14px; }
.dim { color: var(--ink-3); font-size: 12px; }
.empty-hint { font-size: 13px; color: var(--ink-3); padding: 12px 0; }
@media (max-width: 720px) { .imp-grid { grid-template-columns: 1fr; } }
</style>
