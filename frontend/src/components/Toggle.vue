<script setup>
const props = defineProps({ modelValue: Boolean, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <button class="toggle" :class="{ on: modelValue, disabled }" :disabled="disabled"
          @click="emit('update:modelValue', !modelValue)" type="button">
    <span class="knob" />
  </button>
</template>

<style scoped>
.toggle {
  width: 42px; height: 24px; border-radius: 999px; border: none; cursor: pointer;
  background: var(--line-strong); position: relative; transition: background .18s; padding: 0;
}
.toggle.on { background: var(--green); }
.toggle.disabled { opacity: .5; cursor: not-allowed; }
.knob {
  position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%;
  background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.25); transition: left .18s;
}
.toggle.on .knob { left: 21px; }
</style>
