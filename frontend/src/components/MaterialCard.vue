<script setup>
import { ref } from 'vue'
import Icon from './Icon.vue'

const props = defineProps({
  retrieval: Object,        // {mode, materials, policy_files, raw_count, dropped}
  loading: Boolean,
})
const expanded = ref({})

const relClass = { 高: 'badge-green', 较高: 'badge-blue', 一般: 'badge-gray' }

// 仅放行 http/https，防止检索返回的 url 携带 javascript: 等协议造成点击型 XSS
function safeUrl(u) {
  return /^https?:\/\//i.test(u || '') ? u : ''
}

function flash(n) {
  const el = document.getElementById('material-' + n)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  el.classList.remove('flash-target')
  void el.offsetWidth
  el.classList.add('flash-target')
}
defineExpose({ flash })
</script>

<template>
  <section class="card mcard">
    <header class="mcard-head">
      <div class="mcard-title">
        <Icon name="landmark" :size="16" />
        <h3>政策引用</h3>
        <span v-if="retrieval" class="mcard-count">{{ retrieval.materials.length }} 条权威材料</span>
      </div>
    </header>

    <div v-if="loading" class="mcard-body">
      <div v-for="i in 2" :key="i" class="m-skel">
        <div class="skeleton" style="width: 62%; height: 15px" />
        <div class="skeleton" style="width: 40%; height: 12px; margin-top: 8px" />
        <div class="skeleton" style="width: 100%; height: 34px; margin-top: 10px" />
      </div>
    </div>

    <div v-else-if="retrieval" class="mcard-body">
      <article v-for="m in retrieval.materials" :key="m.n" :id="'material-' + m.n" class="material">
        <div class="m-row">
          <span class="m-num">{{ m.n }}</span>
          <div class="m-main">
            <div class="m-title">
              <a v-if="safeUrl(m.url)" :href="safeUrl(m.url)" target="_blank" rel="noopener noreferrer">{{ m.title }}<Icon name="link" :size="12" /></a>
              <span v-else>{{ m.title }}</span>
            </div>
            <div class="m-meta">
              <span v-if="m.private" class="badge badge-green" title="来自本地私有政策库">本地政策库</span>
              <span v-if="m.doc_no" class="badge badge-outline-accent">{{ m.doc_no }}</span>
              <span class="m-src">{{ m.source || '来源不详' }}</span>
              <span v-if="m.region" class="badge badge-gray" title="材料适用地域，请核对是否与诉求地一致">{{ m.region }}</span>
              <span v-if="m.date" class="m-src">{{ m.date }}</span>
              <span v-if="m.reliability" class="badge" :class="relClass[m.reliability] || 'badge-gray'">可信度·{{ m.reliability }}</span>
            </div>
            <div class="m-seg" :class="{ open: expanded[m.n] }">
              <p v-for="(s, i) in m.segments" :key="i"><b v-if="s.title">{{ s.title }}　</b>{{ s.content }}</p>
            </div>
            <button class="m-more" @click="expanded[m.n] = !expanded[m.n]">
              {{ expanded[m.n] ? '收起原文' : '展开原文' }}<Icon name="chevron" :size="12" :style="expanded[m.n] ? 'transform:rotate(180deg)' : ''" />
            </button>
          </div>
        </div>
      </article>

      <div v-if="retrieval.dropped?.length" class="m-dropped">
        已按权威性规则过滤 {{ retrieval.dropped.length }} 条低质来源
      </div>
    </div>
  </section>
</template>

<style scoped>
.mcard { overflow: hidden; }
.mcard-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--line); }
.mcard-title { display: flex; align-items: center; gap: 8px; color: var(--primary); }
.mcard-title h3 { font-size: 15px; font-family: var(--font-serif); color: var(--ink); }
.mcard-count { font-size: 12px; color: var(--ink-3); }
.mcard-body { padding: 6px 18px 12px; }
.m-skel { padding: 12px 0; border-bottom: 1px solid var(--line); }
.m-skel:last-child { border-bottom: none; }
.material { padding: 13px 0; border-bottom: 1px solid var(--line); border-radius: 6px; }
.material:last-of-type { border-bottom: none; }
.m-row { display: flex; gap: 12px; }
.m-num {
  flex: none; width: 22px; height: 22px; margin-top: 1px; border-radius: 50%;
  background: var(--primary); color: #fff; font-size: 12px; font-weight: 600;
  display: grid; place-items: center;
}
.m-main { min-width: 0; flex: 1; }
.m-title { font-weight: 600; font-size: 14.5px; line-height: 1.5; }
.m-title a { color: var(--ink); display: inline-flex; align-items: baseline; gap: 4px; }
.m-title a:hover { color: var(--primary); }
.m-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 5px; }
.m-src { font-size: 12px; color: var(--ink-3); }
.m-seg { margin-top: 8px; color: var(--ink-2); font-size: 13.5px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.m-seg.open { display: block; }
.m-seg p { margin-bottom: 6px; }
.m-seg b { color: var(--ink); }
.m-more { border: none; background: none; color: var(--primary); font-size: 12.5px; cursor: pointer; padding: 4px 0 0; display: inline-flex; align-items: center; gap: 2px; }
.m-dropped { font-size: 12px; color: var(--ink-3); padding: 10px 0 4px; border-top: 1px dashed var(--line); margin-top: 4px; }
</style>
