<template>
  <button
    type="button"
    @click="openDialog"
    class="px-3 py-1.5 rounded bg-rose-950/60 hover:bg-rose-900 border border-rose-500/40 text-rose-300 text-xs font-mono font-bold transition-colors"
    :aria-label="`Eliminar ${projectType === 'reto' ? 'reto' : 'auditoría'} ${projectId}`"
  >
    Eliminar
  </button>
  <Teleport to="body">
    <div v-if="showDialog" class="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" @keydown.esc="closeDialog">
      <div role="dialog" aria-modal="true" aria-labelledby="delete-project-title" aria-describedby="delete-project-description" class="bg-[#0d1322] border border-rose-500/40 rounded-lg max-w-md w-full p-6 space-y-4 shadow-2xl">
        <h2 id="delete-project-title" class="text-lg font-mono font-bold text-white">
          Eliminar {{ projectType === 'reto' ? 'reto' : 'auditoría' }}
        </h2>
        <p id="delete-project-description" class="text-sm text-slate-300">
          Se eliminará <strong class="text-white break-all">{{ projectId }}</strong> junto con sus notas, evidencias, botín, reportes y archivos. Esta acción no se puede deshacer.
        </p>
        <p v-if="error" role="alert" class="text-sm text-rose-300">{{ error }}</p>
        <div class="flex justify-end gap-3 pt-3 border-t border-slate-800">
          <button ref="cancelButton" type="button" @click="closeDialog" :disabled="isDeleting" class="px-4 py-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono disabled:opacity-50">Cancelar</button>
          <button type="button" @click="deleteProject" :disabled="isDeleting" class="px-4 py-2 rounded bg-rose-600 hover:bg-rose-500 text-white text-xs font-mono font-bold disabled:opacity-50">
            {{ isDeleting ? 'Eliminando…' : 'Eliminar definitivamente' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { api } from '../api'

const props = defineProps({
  projectId: { type: String, required: true },
  projectType: { type: String, required: true },
})
const emit = defineEmits(['deleted'])
const showDialog = ref(false)
const isDeleting = ref(false)
const error = ref('')
const cancelButton = ref(null)

async function openDialog() {
  error.value = ''
  showDialog.value = true
  await nextTick()
  cancelButton.value?.focus()
}

function closeDialog() {
  if (!isDeleting.value) showDialog.value = false
}

async function deleteProject() {
  if (isDeleting.value) return
  isDeleting.value = true
  error.value = ''
  try {
    await api.deleteEngagement(props.projectId, props.projectType)
    showDialog.value = false
    emit('deleted', { id: props.projectId, type: props.projectType })
  } catch (err) {
    error.value = err.message
  } finally {
    isDeleting.value = false
  }
}
</script>
