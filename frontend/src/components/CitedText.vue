<script setup>
import { computed } from 'vue'

const props = defineProps({ text: { type: String, default: '' }, streaming: Boolean })
const emit = defineEmits(['cite'])

const CITE_RE = /[\[【〔]\s*(材料|案例)\s*(\d{1,2})\s*[\]】〕]|(材料|案例)(\d{1,2})/g

const parts = computed(() => {
  const out = []
  const paragraphs = (props.text || '').replace(/\r/g, '').split('\n')
  paragraphs.forEach((para, pi) => {
    const seg = []
    let last = 0
    para.replace(CITE_RE, (m, w1, n1, w2, n2, offset) => {
      if (offset > last) seg.push({ t: 'text', v: para.slice(last, offset) })
      seg.push({ t: 'cite', word: w1 || w2, n: Number(n1 || n2) })
      last = offset + m.length
      return m
    })
    if (last < para.length) seg.push({ t: 'text', v: para.slice(last) })
    out.push({ key: pi, seg })
  })
  return out
})

function boldSplit(s) {
  // **x** 轻量加粗
  const seg = []
  let last = 0
  s.replace(/\*\*([^*]+)\*\*/g, (m, inner, offset) => {
    if (offset > last) seg.push({ b: false, v: s.slice(last, offset) })
    seg.push({ b: true, v: inner })
    last = offset + m.length
    return m
  })
  if (last < s.length) seg.push({ b: false, v: s.slice(last) })
  return seg
}
</script>

<template>
  <div class="cited">
    <p v-for="p in parts" :key="p.key" class="cited-p">
      <template v-for="(s, i) in p.seg" :key="i">
        <span v-if="s.t === 'text'">
          <template v-for="(b, j) in boldSplit(s.v)" :key="j">
            <strong v-if="b.b">{{ b.v }}</strong><template v-else>{{ b.v }}</template>
          </template>
        </span>
        <button v-else class="cite-chip" :class="{ case: s.word === '案例' }"
                @click="emit('cite', { word: s.word, n: s.n })">{{ s.word[0] }}{{ s.n }}</button>
      </template>
      <span v-if="streaming && p.key === parts.length - 1" class="stream-cursor" />
    </p>
  </div>
</template>

<style scoped>
.cited-p { min-height: 8px; margin: 0 0 2px; white-space: pre-wrap; word-break: break-word; }
.cite-chip { border: 1px solid var(--primary-line); }
</style>
