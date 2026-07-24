<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api'

const data = ref(null)
const page = ref(1)
async function load() { data.value = await api.get(`/api/admin/audit?page=${page.value}&size=30`) }
onMounted(load)
function go(p) { page.value = p; load() }

const actionName = {
  login: '登录', login_failed: '登录失败', change_password: '修改密码',
  create_user: '创建用户', reset_password: '重置密码', set_user_status: '变更用户状态',
  update_settings: '修改平台参数', llm_test: '测试生成模型连接',
  private_doc_add: '导入私有政策', private_doc_delete: '删除私有政策',
}
</script>

<template>
  <div>
    <div class="a-head">
      <h3>审计日志</h3>
      <p>账号与配置类敏感操作留痕（登录、建号、重置、参数变更）</p>
    </div>
    <div class="card" v-if="data">
      <table class="table">
        <thead><tr><th style="width:160px">时间</th><th style="width:120px">操作人</th><th style="width:140px">动作</th><th>详情</th></tr></thead>
        <tbody>
          <tr v-for="it in data.items" :key="it.id">
            <td class="dim">{{ it.created_at }}</td>
            <td>{{ it.username || '—' }}</td>
            <td>{{ actionName[it.action] || it.action }}</td>
            <td class="dim">{{ it.detail || '—' }}</td>
          </tr>
        </tbody>
      </table>
      <div class="pager" v-if="data.total > data.size">
        <button class="btn btn-plain btn-sm" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
        <span>{{ page }} / {{ Math.ceil(data.total / data.size) }}</span>
        <button class="btn btn-plain btn-sm" :disabled="page >= Math.ceil(data.total / data.size)" @click="go(page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.a-head { margin-bottom: 14px; }
.a-head h3 { font-family: var(--font-serif); font-size: 16px; }
.a-head p { font-size: 12.5px; color: var(--ink-3); margin-top: 4px; }
.dim { color: var(--ink-3); }
.pager { display: flex; align-items: center; justify-content: center; gap: 14px; padding: 14px; font-size: 13px; color: var(--ink-3); }
</style>
