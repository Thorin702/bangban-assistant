<script setup>
import { ref } from 'vue'
import Icon from '../components/Icon.vue'
import AdminOverview from './admin/AdminOverview.vue'
import AdminUsers from './admin/AdminUsers.vue'
import AdminSettings from './admin/AdminSettings.vue'
import AdminPrivateDB from './admin/AdminPrivateDB.vue'
import AdminRecords from './admin/AdminRecords.vue'
import AdminAudit from './admin/AdminAudit.vue'

const tab = ref('overview')
const tabs = [
  { key: 'overview', label: '运行概览', icon: 'chart', comp: AdminOverview },
  { key: 'settings', label: '功能与参数', icon: 'sliders', comp: AdminSettings },
  { key: 'private', label: '私有政策库', icon: 'shield', comp: AdminPrivateDB },
  { key: 'users', label: '用户管理', icon: 'users', comp: AdminUsers },
  { key: 'records', label: '咨询记录', icon: 'file', comp: AdminRecords },
  { key: 'audit', label: '审计日志', icon: 'eye', comp: AdminAudit },
]
</script>

<template>
  <div class="page admin">
    <aside class="a-rail card">
      <div class="a-rail-title">后台管理</div>
      <button v-for="t in tabs" :key="t.key" class="a-tab" :class="{ active: tab === t.key }" @click="tab = t.key">
        <Icon :name="t.icon" :size="15" />{{ t.label }}
      </button>
    </aside>
    <section class="a-content">
      <component :is="tabs.find((t) => t.key === tab).comp" />
    </section>
  </div>
</template>

<style scoped>
.admin { display: grid; grid-template-columns: 200px 1fr; gap: 20px; align-items: start; }
@media (max-width: 860px) { .admin { grid-template-columns: 1fr; } .a-rail { display: flex; overflow-x: auto; position: static !important; } .a-rail-title { display: none; } }
.a-rail { padding: 10px; position: sticky; top: 76px; }
.a-rail-title { font-family: var(--font-serif); font-size: 13px; color: var(--ink-3); padding: 6px 10px 10px; }
.a-tab {
  display: flex; align-items: center; gap: 9px; width: 100%; text-align: left;
  border: none; background: none; padding: 9px 12px; border-radius: 8px; cursor: pointer;
  font-size: 13.5px; color: var(--ink-2); white-space: nowrap;
}
.a-tab:hover { background: var(--bg-deep); color: var(--ink); }
.a-tab.active { background: var(--primary-soft); color: var(--primary); font-weight: 500; }
.a-content { min-width: 0; }
</style>
