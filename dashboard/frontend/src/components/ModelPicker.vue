<template>
  <div class="relative">
    <input
      ref="inputEl"
      type="text"
      role="combobox"
      :aria-expanded="open"
      :aria-controls="listboxId"
      aria-autocomplete="list"
      :aria-activedescendant="activeOptionId"
      :value="open ? query : closedLabel"
      :placeholder="placeholder"
      autocomplete="off"
      class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-2.5 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
      @focus="openPanel"
      @input="onInput"
      @keydown.down.prevent="moveHighlight(1)"
      @keydown.up.prevent="moveHighlight(-1)"
      @keydown.enter.prevent="selectHighlighted"
      @keydown.escape="closePanel"
      @blur="closePanel"
    />

    <div
      v-if="open"
      :id="listboxId"
      role="listbox"
      class="absolute z-50 top-full left-0 mt-1 w-full max-h-72 overflow-y-auto rounded-sm border border-slate-700 bg-[#0b101d] text-xs shadow-xl"
    >
      <p v-if="loading" class="px-3 py-2 text-slate-400">Consultando…</p>
      <p v-else-if="error" role="alert" class="px-3 py-2 text-red-400">{{ error }}</p>
      <p v-else-if="filteredModels.length === 0" class="px-3 py-2 text-slate-500">Sin coincidencias.</p>

      <ul v-if="!loading">
        <li
          v-for="(m, i) in filteredModels"
          :key="m.id"
          :id="optionId(i)"
          role="option"
          :aria-selected="i === highlightedIndex"
          class="px-3 py-1.5 cursor-pointer truncate"
          :class="i === highlightedIndex ? 'bg-cyan-500/20 text-cyan-300' : 'text-slate-200 hover:bg-slate-800'"
          @mousedown.prevent="selectModel(m)"
        >
          {{ m.name }} — {{ m.id }}
        </li>
      </ul>

      <div v-if="!loading" class="border-t border-slate-800">
        <div
          :id="optionId(refreshIndex)"
          role="option"
          :aria-selected="highlightedIndex === refreshIndex"
          class="px-3 py-1.5 cursor-pointer font-bold"
          :class="highlightedIndex === refreshIndex ? 'bg-cyan-500/20 text-cyan-300' : 'text-cyan-400 hover:bg-slate-800'"
          @mousedown.prevent="triggerRefresh"
        >
          🔄 Actualizar modelos
        </div>
        <div
          v-if="allowCustom"
          :id="optionId(customIndex)"
          role="option"
          :aria-selected="highlightedIndex === customIndex"
          class="px-3 py-1.5 cursor-pointer"
          :class="highlightedIndex === customIndex ? 'bg-cyan-500/20 text-cyan-300' : 'text-slate-300 hover:bg-slate-800'"
          @mousedown.prevent="selectCustom"
        >
          ✏️ Modelo personalizado (escribir slug)
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, useId } from 'vue'

// Combobox de modelo compartido entre VaultView (modelo inicial de una llave)
// y ChatView (modelo activo del chat). Reemplaza el <select> + <input> de
// búsqueda + botón de recarga separados por un único campo que es a la vez
// disparador y buscador, con una lista flotante filtrable al teclear y
// navegación por teclado -- igual al selector de modelos de referencia que
// pidió el owner tras probar la versión anterior en vivo.
//
// No conoce nada de red: el padre sigue siendo dueño de `models`/`loading`/
// `error` y de volver a consultar el catálogo cuando se emite "refresh".

const props = defineProps({
  modelValue: { type: String, default: '' },
  models: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  placeholder: { type: String, default: 'Elegir modelo' },
  allowCustom: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'refresh'])

const uid = useId()
const listboxId = `${uid}-listbox`
const inputEl = ref(null)
const open = ref(false)
const query = ref('')
const highlightedIndex = ref(0)

const filteredModels = computed(() => {
  const q = query.value.toLowerCase()
  if (!q) return props.models
  return props.models.filter(m => `${m.name} ${m.id}`.toLowerCase().includes(q))
})

// Índices de las filas fijas al final de la lista filtrable, para que la
// navegación con flechas las recorra como una fila más.
const refreshIndex = computed(() => filteredModels.value.length)
const customIndex = computed(() => filteredModels.value.length + (props.allowCustom ? 1 : 0))
const lastIndex = computed(() => props.allowCustom ? customIndex.value : refreshIndex.value)

const closedLabel = computed(() => {
  if (props.allowCustom && props.modelValue === 'custom') return '✏️ Personalizado'
  const current = props.models.find(m => m.id === props.modelValue)
  return current ? `${current.name} — ${current.id}` : ''
})

const activeOptionId = computed(() => open.value ? optionId(highlightedIndex.value) : undefined)

function optionId(i) {
  return `${uid}-option-${i}`
}

function openPanel() {
  open.value = true
  query.value = ''
  highlightedIndex.value = 0
}

function closePanel() {
  open.value = false
}

function onInput(event) {
  query.value = event.target.value
  highlightedIndex.value = 0
}

function moveHighlight(delta) {
  if (!open.value) {
    openPanel()
    return
  }
  const max = lastIndex.value
  let next = highlightedIndex.value + delta
  if (next < 0) next = max
  if (next > max) next = 0
  highlightedIndex.value = next
}

function selectHighlighted() {
  if (!open.value) return
  const i = highlightedIndex.value
  if (i === refreshIndex.value) {
    triggerRefresh()
  } else if (props.allowCustom && i === customIndex.value) {
    selectCustom()
  } else {
    const m = filteredModels.value[i]
    if (m) selectModel(m)
  }
}

function selectModel(m) {
  emit('update:modelValue', m.id)
  closePanel()
  inputEl.value?.blur()
}

function selectCustom() {
  emit('update:modelValue', 'custom')
  closePanel()
  inputEl.value?.blur()
}

function triggerRefresh() {
  emit('refresh')
  // Deliberadamente NO se cierra el panel: el operador probablemente quiere
  // ver la lista recién consultada de inmediato.
  highlightedIndex.value = 0
}
</script>
