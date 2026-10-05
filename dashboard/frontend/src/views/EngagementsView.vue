<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#1b253b] pb-6">
      <div>
        <h1 class="text-2xl font-mono font-bold text-white flex items-center space-x-3">
          <span>📁 Auditorías & Retos Técnicos</span>
          <span class="text-xs px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-mono">
            /workspace
          </span>
        </h1>
        <p class="text-slate-400 text-sm mt-1">
          Espacio de trabajo sincronizado en tiempo real con el sistema de archivos del laboratorio.
        </p>
      </div>

      <button
        @click="showModal = true"
        class="px-4 py-2 rounded bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-semibold text-sm transition-all shadow-md shadow-cyan-500/20 flex items-center justify-center space-x-2"
      >
        <span>+</span>
        <span>Inicializar Auditoría (pt-eng)</span>
      </button>
    </div>

    <!-- Filtros y Búsqueda -->
    <div class="flex flex-col sm:flex-row items-center justify-between gap-4 bg-[#0d1322] border border-[#1b253b] p-3 rounded-lg">
      <div class="flex items-center space-x-2 w-full sm:w-auto">
        <button
          v-for="f in ['all', 'engagement', 'reto']"
          :key="f"
          @click="currentFilter = f"
          class="px-3 py-1 rounded text-xs font-mono uppercase tracking-wider transition-colors"
          :class="currentFilter === f ? 'bg-cyan-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white bg-slate-800/60'"
        >
          {{ f === 'all' ? 'Todos' : (f === 'engagement' ? 'Auditorías' : 'Retos / CTFs') }}
        </button>
      </div>

      <div class="w-full sm:w-72">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Buscar por nombre, cliente..."
          class="w-full bg-[#070b14] border border-[#1b253b] focus:border-cyan-400 rounded px-3 py-1.5 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-none"
        />
      </div>
    </div>

    <!-- Lista / Grid de Proyectos -->
    <div v-if="isLoading" class="text-center py-12 text-slate-400 font-mono text-sm">
      Cargando auditorías desde /workspace...
    </div>

    <div v-else-if="filteredEngagements.length === 0" class="text-center py-16 tactical-card space-y-3">
      <div class="text-4xl">📂</div>
      <p class="text-slate-300 font-mono text-sm">No se encontraron proyectos con los filtros actuales.</p>
      <button
        @click="showModal = true"
        class="px-4 py-2 rounded bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-mono font-bold text-xs"
      >
        Crear Nuevo Proyecto
      </button>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      <div
        v-for="item in filteredEngagements"
        :key="item.id"
        class="tactical-card flex flex-col justify-between group hover:border-cyan-500/50"
      >
        <div>
          <div class="flex items-center justify-between">
            <span
              class="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider"
              :class="item.type === 'reto' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'"
            >
              {{ item.type }}
            </span>
            <span class="text-xs font-mono text-slate-500">{{ item.created_at }}</span>
          </div>

          <h3 class="text-lg font-mono font-bold text-white mt-3 group-hover:text-cyan-300 transition-colors">
            {{ item.name }}
          </h3>
          <p class="text-xs text-slate-400 mt-1 flex items-center space-x-1 font-mono">
            <span>Cliente/Objetivo:</span>
            <span class="text-slate-200 font-medium">{{ item.client_or_platform }}</span>
          </p>

          <div class="mt-4 pt-3 border-t border-slate-800 grid grid-cols-2 gap-2 text-xs font-mono text-slate-300">
            <div class="bg-slate-900/60 p-2 rounded border border-slate-800/80">
              <span class="text-slate-400 block text-[10px]">EVIDENCIAS</span>
              <span class="text-sm font-bold text-amber-300">{{ item.evidence_count }} hallazgos</span>
            </div>
            <div class="bg-slate-900/60 p-2 rounded border border-slate-800/80">
              <span class="text-slate-400 block text-[10px]">TERMINAL LOG</span>
              <span class="text-sm font-bold text-cyan-300">{{ item.terminal_log_lines }} líneas</span>
            </div>
          </div>
        </div>

        <div class="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between">
          <span class="text-[11px] font-mono text-slate-500 truncate max-w-[150px]">
            {{ item.has_target_yaml ? 'target.yaml ✓' : 'sin scope' }}
          </span>
          <router-link
            :to="`/engagements/${item.type}/${item.id}`"
            class="px-3 py-1.5 rounded bg-slate-800 hover:bg-cyan-500 hover:text-slate-950 text-cyan-300 text-xs font-mono font-bold transition-all border border-slate-700 hover:border-cyan-400"
          >
            Abrir Espacio &rarr;
          </router-link>
        </div>
      </div>
    </div>

    <!-- Modal Inicializar Engagement -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
    >
      <div class="bg-[#0d1322] border border-cyan-500/40 rounded-lg max-w-lg w-full p-6 shadow-2xl space-y-5">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 class="text-lg font-mono font-bold text-white flex items-center space-x-2">
            <span>⚡ Inicializar Nueva Auditoría (pt-eng)</span>
          </h2>
          <button @click="showModal = false" class="text-slate-400 hover:text-white font-mono text-lg">&times;</button>
        </div>

        <form @submit.prevent="submitCreate" class="space-y-4">
          <div>
            <label class="block text-xs font-mono text-slate-300 mb-1">Nombre / Identificador único (Slug):</label>
            <input
              v-model="newForm.name"
              type="text"
              required
              placeholder="acme-corp, reto-ciber, banco-xyz"
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded px-3 py-2 text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-none"
            />
            <p class="text-[10px] text-slate-500 mt-1 font-mono">Solo letras, números, puntos y guiones.</p>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">Tipo de Proyecto:</label>
              <select
                v-model="newForm.type"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded px-3 py-2 text-sm font-mono text-slate-100 focus:outline-none"
              >
                <option value="engagement">Auditoría / Pentest</option>
                <option value="reto">Reto / CTF</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">Dominio / Host Inicial:</label>
              <input
                v-model="newForm.domain"
                type="text"
                placeholder="acme.local, target.com"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded px-3 py-2 text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label class="block text-xs font-mono text-slate-300 mb-1">Cliente u Organización Objetivo:</label>
            <input
              v-model="newForm.client"
              type="text"
              placeholder="Acme Corporation, HackTheBox, Bugcrowd"
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded px-3 py-2 text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-none"
            />
          </div>

          <div v-if="createError" class="p-3 rounded bg-red-950/50 border border-red-500/40 text-red-300 text-xs font-mono">
            {{ createError }}
          </div>

          <div class="pt-3 border-t border-slate-800 flex items-center justify-end space-x-3">
            <button
              type="button"
              @click="showModal = false"
              class="px-4 py-2 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 font-mono text-xs"
            >
              Cancelar
            </button>
            <button
              type="submit"
              :disabled="isSubmitting"
              class="px-5 py-2 rounded bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs disabled:opacity-50 transition-all shadow-md shadow-cyan-500/20"
            >
              {{ isSubmitting ? 'Creando...' : 'Crear Proyecto' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'

const engagements = ref([])
const isLoading = ref(true)
const currentFilter = ref('all')
const searchQuery = ref('')

const showModal = ref(false)
const isSubmitting = ref(false)
const createError = ref('')
const newForm = ref({
  name: '',
  type: 'engagement',
  domain: '',
  client: '',
})

const filteredEngagements = computed(() => {
  return engagements.value.filter(item => {
    const matchesFilter = currentFilter.value === 'all' || item.type === currentFilter.value
    const matchesSearch = !searchQuery.value.trim() ||
      item.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      (item.client_or_platform && item.client_or_platform.toLowerCase().includes(searchQuery.value.toLowerCase()))
    return matchesFilter && matchesSearch
  })
})

async function loadEngagements() {
  isLoading.value = true
  try {
    engagements.value = await api.getEngagements()
  } catch (err) {
    console.error('Error al cargar auditorías:', err)
  } finally {
    isLoading.value = false
  }
}

async function submitCreate() {
  if (!newForm.value.name.trim()) return
  isSubmitting.value = true
  createError.value = ''
  try {
    await api.createEngagement(newForm.value)
    showModal.value = false
    newForm.value = { name: '', type: 'engagement', domain: '', client: '' }
    await loadEngagements()
  } catch (err) {
    createError.value = err.message
  } finally {
    isSubmitting.value = false
  }
}

onMounted(() => {
  loadEngagements()
})
</script>
