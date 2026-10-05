<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#1b253b] pb-6">
      <div>
        <h1 class="text-2xl font-mono font-bold text-white">Papelera de proyectos</h1>
        <p class="text-slate-400 text-sm mt-2 max-w-2xl">Las auditorías y retos eliminados conservan sus notas, evidencias, botín y reportes. Restaura una copia cuando no exista un proyecto con el mismo nombre y tipo.</p>
      </div>
      <router-link to="/engagements" class="px-4 py-2 rounded-sm border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700 font-mono text-sm text-center">Volver a proyectos</router-link>
    </div>

    <div v-if="notice" role="status" class="p-4 rounded-sm border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-sm">
      {{ notice }}
      <router-link v-if="restoredProject" :to="`/engagements/${restoredProject.type}/${encodeURIComponent(restoredProject.project_id)}`" class="ml-2 underline font-mono">Abrir proyecto</router-link>
    </div>
    <div v-if="error" role="alert" class="p-4 rounded-sm border border-rose-500/40 bg-rose-950/50 text-rose-300 text-sm">{{ error }}</div>
    <div class="flex items-center justify-between gap-4 text-sm">
      <p class="text-slate-400">{{ entries.length }} {{ entries.length === 1 ? 'copia disponible' : 'copias disponibles' }} · Sin eliminación automática</p>
      <button type="button" @click="loadTrash" :disabled="isLoading || Boolean(restoring)" class="px-3 py-2 rounded-sm bg-slate-800 text-slate-200 hover:bg-slate-700 font-mono text-xs disabled:opacity-50">Actualizar</button>
    </div>
    <p v-if="isLoading" class="text-center py-12 text-slate-400 font-mono text-sm">Cargando papelera…</p>
    <div v-else-if="!entries.length && !error" class="tactical-card text-center py-12 space-y-2">
      <p class="text-white font-mono">La papelera está vacía</p>
      <p class="text-slate-400 text-sm">Los proyectos que elimines desde el dashboard aparecerán aquí.</p>
    </div>
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      <article v-for="entry in entries" :key="`${entry.type}/${entry.project_id}/${entry.entry_id}`" class="tactical-card flex flex-col justify-between gap-5">
        <div class="space-y-3">
          <span class="inline-block px-2 py-1 rounded-sm text-xs font-mono border" :class="entry.type === 'reto' ? 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10' : 'text-cyan-300 border-cyan-500/30 bg-cyan-500/10'">{{ entry.type === 'reto' ? 'Reto / CTF' : 'Auditoría' }}</span>
          <h2 class="text-lg font-mono font-bold text-white break-all">{{ entry.project_id }}</h2>
          <p class="text-slate-400 text-xs">Eliminado: <time :datetime="entry.deleted_at">{{ formatDate(entry.deleted_at) }}</time></p>
        </div>
        <button type="button" @click="restoreProject(entry)" :disabled="Boolean(restoring)" :aria-label="`Restaurar ${entry.project_id} eliminado el ${formatDate(entry.deleted_at)}`" class="w-full px-4 py-2 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-sm disabled:opacity-50">{{ restoring === entry.entry_id ? 'Restaurando…' : 'Restaurar proyecto' }}</button>
      </article>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const entries = ref([])
const isLoading = ref(true)
const restoring = ref('')
const error = ref('')
const notice = ref('')
const restoredProject = ref(null)

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'medium' })
}

async function loadTrash() {
  if (restoring.value) return
  isLoading.value = true
  error.value = ''
  try {
    entries.value = await api.getTrash()
  } catch (err) {
    error.value = err.message
  } finally {
    isLoading.value = false
  }
}

async function restoreProject(entry) {
  if (restoring.value) return
  restoring.value = entry.entry_id
  error.value = ''
  notice.value = ''
  restoredProject.value = null
  try {
    await api.restoreProject(entry)
    entries.value = entries.value.filter(item => item.entry_id !== entry.entry_id || item.project_id !== entry.project_id || item.type !== entry.type)
    restoredProject.value = entry
    notice.value = `Se restauró ${entry.project_id}. Sus archivos vuelven a estar disponibles.`
  } catch (err) {
    error.value = err.message
  } finally {
    restoring.value = ''
  }
}

onMounted(loadTrash)
</script>
