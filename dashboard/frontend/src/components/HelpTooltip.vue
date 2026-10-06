<template>
  <span class="relative inline-flex items-center normal-case font-sans">
    <button
      type="button"
      class="ml-1 w-4 h-4 shrink-0 inline-flex items-center justify-center rounded-full border border-slate-600 text-[10px] leading-none text-slate-400 hover:text-cyan-400 hover:border-cyan-400 focus:text-cyan-400 focus:border-cyan-400 focus:outline-hidden"
      :aria-label="`Qué significa ${label}`"
      :aria-expanded="open ? 'true' : 'false'"
      @click="open = !open"
      @keydown.escape="open = false"
      @blur="open = false"
    >?</button>
    <div
      v-if="open"
      role="tooltip"
      class="absolute z-50 top-full left-0 mt-1 w-64 p-2.5 rounded-sm border border-slate-700 bg-[#0b101d] text-xs leading-relaxed text-slate-300 shadow-xl normal-case tracking-normal font-sans"
    >
      <p class="font-bold text-cyan-300 mb-1">{{ label }}</p>
      <p><slot /></p>
    </div>
  </span>
</template>

<script setup>
import { ref } from 'vue'

// Ayuda contextual corta para la jerga del dashboard (Scope Guard,
// Evidence-First, control negativo, patrones gf...). Fase 112 / backlog
// A8: antes estos términos aparecían sin explicación en la interfaz.
defineProps({
  label: { type: String, required: true },
})

const open = ref(false)
</script>
