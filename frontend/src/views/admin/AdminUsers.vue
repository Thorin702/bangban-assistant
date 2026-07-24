<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api'
import { toast } from '../../toast'
import { copyToClipboard } from '../../clipboard'
import Icon from '../../components/Icon.vue'
import Modal from '../../components/Modal.vue'

const users = ref([])
const showCreate = ref(false)
const createForm = ref({ username: '', display_name: '', org: '', role: 'handler' })
const tempPw = ref(null)     // {username, password, mode}
const busy = ref(false)

const roleName = { handler: '承办人', mediator: '调解员', admin: '管理员' }

onMounted(load)
async function load() { users.value = await api.get('/api/admin/users') }

async function create() {
  if (!createForm.value.username || !createForm.value.display_name) return toast('请填写账号与姓名', 'warn')
  busy.value = true
  try {
    const r = await api.post('/api/admin/users', createForm.value)
    tempPw.value = { username: createForm.value.username, password: r.temp_password, mode: '新建' }
    showCreate.value = false
    createForm.value = { username: '', display_name: '', org: '', role: 'handler' }
    load()
  } catch (e) { toast(e.message, 'err') } finally { busy.value = false }
}

async function resetPw(u) {
  if (!confirm(`确认重置 ${u.display_name}（${u.username}）的密码？`)) return
  const r = await api.post(`/api/admin/users/${u.id}/reset-password`)
  tempPw.value = { username: u.username, password: r.temp_password, mode: '重置' }
  load()
}

async function toggleStatus(u) {
  const next = u.status === 'active' ? 'disabled' : 'active'
  try {
    await api.post(`/api/admin/users/${u.id}/status`, { status: next })
    toast(next === 'active' ? '已启用' : '已停用', 'ok')
    load()
  } catch (e) { toast(e.message, 'err') }
}

async function copyPw() {
  const ok = await copyToClipboard(`${tempPw.value.username} / ${tempPw.value.password}`)
  toast(ok ? '已复制' : '复制失败，请手动记录', ok ? 'ok' : 'warn')
}
</script>

<template>
  <div class="us">
    <div class="us-head">
      <div>
        <h3>用户管理</h3>
        <p>试点期由管理员预建账号；初始/重置密码仅显示一次，首次登录强制改密</p>
      </div>
      <button class="btn btn-primary" @click="showCreate = true"><Icon name="plus" :size="14" />新建账号</button>
    </div>

    <div class="card">
      <table class="table">
        <thead><tr><th>账号</th><th>姓名</th><th>单位</th><th>角色</th><th>状态</th><th>最近登录</th><th style="width:170px">操作</th></tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td><code class="mono">{{ u.username }}</code></td>
            <td>{{ u.display_name }}</td>
            <td class="dim">{{ u.org || '—' }}</td>
            <td><span class="badge" :class="u.role === 'admin' ? 'badge-blue' : 'badge-gray'">{{ roleName[u.role] }}</span></td>
            <td>
              <span class="badge" :class="u.status === 'active' ? 'badge-green' : 'badge-red'">{{ u.status === 'active' ? '正常' : '停用' }}</span>
              <span v-if="u.must_change_password" class="badge badge-amber" title="尚未完成首次改密">待改密</span>
            </td>
            <td class="dim">{{ u.last_login_at || '从未登录' }}</td>
            <td>
              <div class="ops">
                <button class="btn btn-plain btn-sm" @click="resetPw(u)">重置密码</button>
                <button class="btn btn-sm" :class="u.status === 'active' ? 'btn-danger' : 'btn-ghost'" @click="toggleStatus(u)">
                  {{ u.status === 'active' ? '停用' : '启用' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <Modal v-if="showCreate" title="新建账号" @close="showCreate = false">
      <div class="cform">
        <div><label class="field-label">登录账号（字母/数字）</label><input class="input" v-model.trim="createForm.username" placeholder="如 zhang.san" /></div>
        <div><label class="field-label">姓名</label><input class="input" v-model.trim="createForm.display_name" placeholder="张三" /></div>
        <div><label class="field-label">单位</label><input class="input" v-model.trim="createForm.org" placeholder="市中区政务服务中心" /></div>
        <div>
          <label class="field-label">角色</label>
          <select class="select" v-model="createForm.role">
            <option value="handler">承办人（12345 工单）</option>
            <option value="mediator">调解员（矛盾调解）</option>
            <option value="admin">管理员</option>
          </select>
        </div>
      </div>
      <template #footer>
        <button class="btn btn-plain" @click="showCreate = false">取消</button>
        <button class="btn btn-primary" :disabled="busy" @click="create">创建</button>
      </template>
    </Modal>

    <Modal v-if="tempPw" :title="tempPw.mode + '成功 · 初始密码'" @close="tempPw = null">
      <p class="pw-note">请立即转交给使用人，此密码<b>仅显示这一次</b>；首次登录会强制修改。</p>
      <div class="pw-box">
        <div><span class="pw-label">账号</span><code class="mono big">{{ tempPw.username }}</code></div>
        <div><span class="pw-label">初始密码</span><code class="mono big">{{ tempPw.password }}</code></div>
      </div>
      <template #footer>
        <button class="btn btn-ghost" @click="copyPw"><Icon name="copy" :size="14" />复制</button>
        <button class="btn btn-primary" @click="tempPw = null">我已转交</button>
      </template>
    </Modal>
  </div>
</template>

<style scoped>
.us-head { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 14px; gap: 12px; flex-wrap: wrap; }
.us-head h3 { font-family: var(--font-serif); font-size: 16px; }
.us-head p { font-size: 12.5px; color: var(--ink-3); margin-top: 4px; }
.mono { font-family: var(--font-mono); font-size: 12.5px; }
.mono.big { font-size: 16px; font-weight: 600; }
.dim { color: var(--ink-3); }
.ops { display: flex; gap: 6px; }
.cform { display: flex; flex-direction: column; gap: 12px; }
.pw-note { font-size: 13px; color: var(--ink-2); margin-bottom: 12px; }
.pw-note b { color: var(--accent); }
.pw-box { background: var(--bg); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.pw-label { display: inline-block; width: 74px; font-size: 12.5px; color: var(--ink-3); }
</style>
