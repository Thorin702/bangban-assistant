<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../api'
import Icon from '../../components/Icon.vue'

const router = useRouter()
const data = ref(null)
const page = ref(1)
const filters = ref({ status: '', username: '', q: '' })

async function load() {
  const p = new URLSearchParams({ page: page.value, size: 20, ...filters.value })
  data.value = await api.get('/api/admin/consults?' + p.toString())
}
onMounted(load)
function search() { page.value = 1; load() }
function go(p) { page.value = p; load() }

const statusMeta = {
  done: ['已完成', 'badge-green'], empty: ['无材料', 'badge-gray'],
  error: ['失败', 'badge-red'], running: ['进行中', 'badge-blue'],
}
const secName = { interpret: '解释', reply: '话术', method: '办法', experience: '经验' }
const decC = { adopt: 'dd-adopt', modify: 'dd-modify', reject: 'dd-reject' }
</script>

<template>
  <div class="rec">
    <div class="rec-head">
      <div>
        <h3>咨询记录（全量留痕）</h3>
        <p>谁发起、依据什么材料、AI 给了什么、人最终怎么决定——全程可回放</p>
      </div>
    </div>

    <div class="card filters">
      <input class="input" style="max-width: 160px" v-model.trim="filters.username" placeholder="按账号筛选" @keyup.enter="search" />
      <select class="select" style="max-width: 140px" v-model="filters.status" @change="search">
        <option value="">全部状态</option>
        <option value="done">已完成</option>
        <option value="empty">无材料</option>
        <option value="error">失败</option>
      </select>
      <input class="input" style="flex:1; min-width: 160px" v-model.trim="filters.q" placeholder="按诉求关键词搜索" @keyup.enter="search" />
      <button class="btn btn-ghost" @click="search"><Icon name="search" :size="14" />查询</button>
    </div>

    <div class="card" v-if="data">
      <table class="table">
        <thead><tr><th style="width:64px">#</th><th>诉求摘要</th><th>发起人</th><th>决策</th><th>状态</th><th>模式</th><th style="width:150px">时间</th></tr></thead>
        <tbody>
          <tr v-for="it in data.items" :key="it.id" class="r-row" @click="router.push('/history/' + it.id)">
            <td class="dim">{{ it.id }}</td>
            <td class="r-ex">{{ it.excerpt }}</td>
            <td>{{ it.display_name }}<div class="dim mono-sm">{{ it.username }}</div></td>
            <td>
              <span v-for="(d, s) in it.decisions" :key="s" class="h-dec" :class="decC[d]">{{ secName[s] }}</span>
              <span v-if="!Object.keys(it.decisions).length" class="dim">—</span>
            </td>
            <td><span class="badge" :class="statusMeta[it.status]?.[1]">{{ statusMeta[it.status]?.[0] }}</span></td>
            <td><span class="badge" :class="it.retrieval_mode === 'mock' ? 'badge-amber' : 'badge-green'">{{ it.retrieval_mode === 'mock' ? '演示' : '真实' }}</span></td>
            <td class="dim">{{ it.created_at }}</td>
          </tr>
        </tbody>
      </table>
      <div class="pager" v-if="data.total > data.size">
        <button class="btn btn-plain btn-sm" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
        <span>{{ page }} / {{ Math.ceil(data.total / data.size) }}（共 {{ data.total }} 条）</span>
        <button class="btn btn-plain btn-sm" :disabled="page >= Math.ceil(data.total / data.size)" @click="go(page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rec-head { margin-bottom: 14px; }
.rec-head h3 { font-family: var(--font-serif); font-size: 16px; }
.rec-head p { font-size: 12.5px; color: var(--ink-3); margin-top: 4px; }
.filters { display: flex; gap: 10px; padding: 12px 14px; margin-bottom: 14px; flex-wrap: wrap; }
.r-row { cursor: pointer; }
.r-ex { max-width: 340px; }
.dim { color: var(--ink-3); }
.mono-sm { font-family: var(--font-mono); font-size: 11px; }
.h-dec { font-size: 11px; padding: 2px 6px; border-radius: 5px; margin-right: 4px; }
.dd-adopt { background: var(--green-soft); color: var(--green); }
.dd-modify { background: var(--primary-soft); color: var(--primary); }
.dd-reject { background: var(--bg-deep); color: var(--ink-3); }
.pager { display: flex; align-items: center; justify-content: center; gap: 14px; padding: 14px; font-size: 13px; color: var(--ink-3); }
</style>
