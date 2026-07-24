<script setup>
defineProps({ title: String, width: { type: String, default: '460px' } })
const emit = defineEmits(['close'])
</script>

<template>
  <Teleport to="body">
    <div class="modal-mask" @mousedown.self="emit('close')">
      <div class="modal" :style="{ maxWidth: width }">
        <div class="modal-head">
          <h3>{{ title }}</h3>
          <button class="modal-x" @click="emit('close')">✕</button>
        </div>
        <div class="modal-body"><slot /></div>
        <div v-if="$slots.footer" class="modal-foot"><slot name="footer" /></div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-mask {
  position: fixed; inset: 0; background: rgba(29, 39, 51, 0.4);
  display: flex; align-items: flex-start; justify-content: center;
  padding: 10vh 16px 16px; z-index: 100; backdrop-filter: blur(2px);
}
.modal { background: #fff; border-radius: var(--radius); width: 100%; box-shadow: var(--shadow-pop); animation: pop .18s ease; }
@keyframes pop { from { opacity: 0; transform: translateY(10px) scale(.98); } }
.modal-head { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px 0; }
.modal-head h3 { font-size: 16px; font-family: var(--font-serif); }
.modal-x { border: none; background: none; color: var(--ink-3); cursor: pointer; font-size: 14px; padding: 4px; }
.modal-x:hover { color: var(--ink); }
.modal-body { padding: 16px 20px; }
.modal-foot { padding: 0 20px 18px; display: flex; justify-content: flex-end; gap: 10px; }
</style>
