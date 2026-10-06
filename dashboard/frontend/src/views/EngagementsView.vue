<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#1b253b] pb-6">
      <div>
        <h1 class="text-2xl font-mono font-bold text-white flex items-center space-x-3">
          <span>📁 Auditorías & Retos Técnicos</span>
          <span class="text-xs px-2 py-0.5 rounded-sm bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-mono">
            /workspace
          </span>
        </h1>
        <p class="text-slate-400 text-sm mt-1">
          Espacio de trabajo sincronizado en tiempo real con el sistema de archivos del laboratorio.
        </p>
      </div>

      <div class="flex flex-wrap gap-3">
      <router-link to="/trash" class="px-4 py-2 rounded-sm border border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700 font-mono text-sm">Papelera</router-link>
      <button
        @click="showModal = true"
        class="px-4 py-2 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-semibold text-sm transition-all shadow-md shadow-cyan-500/20 flex items-center justify-center space-x-2"
      >
        <span>+</span>
        <span>Inicializar Auditoría (pt-eng)</span>
      </button>
      </div>
    </div>

    <!-- Filtros y Búsqueda -->
    <div class="space-y-3 bg-[#0d1322] border border-[#1b253b] p-3 rounded-lg">
      <div class="flex flex-col sm:flex-row items-center justify-between gap-4">
        <div class="flex items-center space-x-2 w-full sm:w-auto">
          <button
            v-for="f in ['all', 'engagement', 'reto']"
            :key="f"
            @click="currentFilter = f"
            class="px-3 py-1 rounded-sm text-xs font-mono uppercase tracking-wider transition-colors"
            :class="currentFilter === f ? 'bg-cyan-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white bg-slate-800/60'"
          >
            {{ f === 'all' ? 'Todos' : (f === 'engagement' ? 'Auditorías' : 'Retos / CTFs') }}
          </button>
        </div>

        <div class="w-full sm:w-72">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Buscar por nombre, cliente, categoría..."
            class="w-full bg-[#070b14] border border-[#1b253b] focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-200 placeholder-slate-500 focus:outline-hidden"
          />
        </div>
      </div>

      <!-- Barra de Subcategorías CTF (visible en Retos o Todos) -->
      <div v-if="currentFilter === 'reto' || currentFilter === 'all'" class="flex flex-wrap items-center gap-1.5 pt-2 border-t border-slate-800/60 text-[11px] font-mono">
        <span class="text-slate-500 mr-1 text-[10px] uppercase">Categoría CTF:</span>
        <button
          v-for="cat in ctfCategories"
          :key="cat.id"
          @click="currentCategory = cat.id"
          class="px-2 py-0.5 rounded-sm transition-all"
          :class="currentCategory === cat.id ? 'bg-slate-700 text-cyan-300 font-bold border border-cyan-500/40' : 'bg-slate-900/60 text-slate-400 hover:text-slate-200 border border-slate-800/80'"
        >
          {{ cat.label }}
        </button>
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
        class="px-4 py-2 rounded-sm bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-mono font-bold text-xs"
      >
        Crear Nuevo Proyecto
      </button>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      <div
        v-for="item in filteredEngagements"
        :key="`${item.type}/${item.id}`"
        class="tactical-card flex flex-col justify-between group hover:border-cyan-500/50"
      >
        <div>
          <div class="flex items-center justify-between flex-wrap gap-1.5">
            <div class="flex items-center flex-wrap gap-1.5">
              <span
                class="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold uppercase tracking-wider"
                :class="item.type === 'reto' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'"
              >
                {{ item.type }}
              </span>
              <span
                v-if="item.type === 'reto' && item.subtype === 'jeopardy' && item.category"
                class="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold uppercase tracking-wider"
                :class="getCategoryBadgeClass(item.category)"
              >
                {{ item.category }}
              </span>
              <span
                v-else-if="item.type === 'reto' && item.subtype === 'machine'"
                class="px-1.5 py-0.5 rounded-sm text-[10px] font-mono bg-teal-500/10 text-teal-300 border border-teal-500/30"
              >
                MÁQUINA
              </span>
              <span
                v-if="item.type === 'reto' && item.points"
                class="px-1.5 py-0.5 rounded-sm text-[10px] font-mono font-bold bg-amber-500/10 text-amber-300 border border-amber-500/30"
              >
                {{ item.points }} pts
              </span>
              <span
                v-if="item.type === 'reto' && item.is_solved"
                class="px-1.5 py-0.5 rounded-sm text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
              >
                ✓ RESUELTO
              </span>
            </div>
            <span class="text-xs font-mono text-slate-500">{{ item.created_at }}</span>
          </div>

          <h3 class="text-lg font-mono font-bold text-white mt-3 group-hover:text-cyan-300 transition-colors">
            {{ item.name }}
          </h3>
          <p class="text-xs text-slate-400 mt-1 flex items-center space-x-1 font-mono">
            <span>{{ item.type === 'reto' ? 'Evento / Plataforma:' : 'Cliente / Organización:' }}</span>
            <span class="text-slate-200 font-medium">{{ item.client_or_platform }}</span>
          </p>

          <div class="mt-4 pt-3 border-t border-slate-800 grid grid-cols-2 gap-2 text-xs font-mono text-slate-300">
            <div class="bg-slate-900/60 p-2 rounded-sm border border-slate-800/80">
              <span class="text-slate-400 block text-[10px]">EVIDENCIAS</span>
              <span class="text-sm font-bold text-amber-300">{{ item.evidence_count }} hallazgos</span>
            </div>
            <div class="bg-slate-900/60 p-2 rounded-sm border border-slate-800/80">
              <span class="text-slate-400 block text-[10px]">TERMINAL LOG</span>
              <span class="text-sm font-bold text-cyan-300">{{ item.terminal_log_lines }} líneas</span>
            </div>
          </div>
        </div>

        <div class="mt-5 pt-3 border-t border-slate-800/80 flex flex-wrap gap-2 items-center justify-between">
          <span class="text-[11px] font-mono text-slate-500 truncate">
            {{ item.has_target_yaml ? 'target.yaml ✓' : 'sin scope' }}
          </span>
          <div class="flex items-center gap-2">
            <DeleteProjectButton :project-id="item.id" :project-type="item.type" @deleted="removeProject" />
            <router-link
              :to="`/engagements/${item.type}/${item.id}`"
              class="px-3 py-1.5 rounded-sm bg-slate-800 hover:bg-cyan-500 hover:text-slate-950 text-cyan-300 text-xs font-mono font-bold transition-all border border-slate-700 hover:border-cyan-400"
            >
              Abrir Espacio &rarr;
            </router-link>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal Inicializar Engagement -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4"
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
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-2 text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-hidden"
            />
            <p class="text-[10px] text-slate-500 mt-1 font-mono">Solo letras, números, puntos y guiones.</p>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">Tipo de Proyecto:</label>
              <select
                v-model="newForm.type"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-2 text-sm font-mono text-slate-100 focus:outline-hidden"
              >
                <option value="engagement">Auditoría / Pentest</option>
                <option value="reto">Reto / CTF</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">{{ newForm.type === 'reto' && newForm.subtype === 'jeopardy' ? 'Host / Enlace del Reto:' : 'Dominio / Host Inicial:' }}</label>
              <input
                v-model="newForm.domain"
                type="text"
                :placeholder="newForm.type === 'reto' && newForm.subtype === 'jeopardy' ? 'ctf.target.org:1337, http://...' : 'acme.local, target.com'"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-2 text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-hidden"
              />
            </div>
          </div>

          <!-- Opciones Específicas para Reto / CTF -->
          <div v-if="newForm.type === 'reto'" class="space-y-3 p-3 bg-slate-900/60 rounded-md border border-slate-800">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-mono text-amber-300 mb-1">Formato de Reto:</label>
                <select
                  v-model="newForm.subtype"
                  class="w-full bg-[#070b14] border border-slate-700 focus:border-amber-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
                >
                  <option value="jeopardy">CTF Jeopardy (Web, Crypto, Pwn...)</option>
                  <option value="machine">Máquina / Boot2Root (HTB, THM...)</option>
                </select>
              </div>
              <div v-if="newForm.subtype === 'jeopardy'">
                <label class="block text-xs font-mono text-amber-300 mb-1">Categoría Técnica:</label>
                <select
                  v-model="newForm.category"
                  class="w-full bg-[#070b14] border border-slate-700 focus:border-amber-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
                >
                  <option value="web">🌐 Web Exploitation</option>
                  <option value="crypto">🔐 Criptografía</option>
                  <option value="pwn">💥 Binary Exploitation (Pwn)</option>
                  <option value="reverse">🔍 Ingeniería Inversa</option>
                  <option value="forensics">🔬 Forense / DFIR</option>
                  <option value="misc">🧩 Misceláneos (Misc)</option>
                  <option value="osint">👁️ OSINT</option>
                </select>
              </div>
            </div>

            <div v-if="newForm.subtype === 'jeopardy'" class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-mono text-slate-400 mb-1">Puntos CTF:</label>
                <input
                  v-model.number="newForm.points"
                  type="number"
                  placeholder="100, 250, 500"
                  class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-hidden"
                />
              </div>
              <div>
                <label class="block text-xs font-mono text-slate-400 mb-1">Dificultad:</label>
                <select
                  v-model="newForm.difficulty"
                  class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
                >
                  <option value="easy">Fácil</option>
                  <option value="medium">Media</option>
                  <option value="hard">Difícil</option>
                  <option value="insane">Insane</option>
                </select>
              </div>
            </div>
          </div>

          <div>
            <label class="block text-xs font-mono text-slate-300 mb-1">{{ newForm.type === 'reto' ? 'Evento / Torneo / Plataforma CTF:' : 'Cliente u Organización Objetivo:' }}</label>
            <input
              v-model="newForm.client"
              type="text"
              :placeholder="newForm.type === 'reto' ? 'DiceCTF 2026, PicoCTF, HackTheBox' : 'Acme Corporation, Bugcrowd'"
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-2 text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-hidden"
            />
          </div>

          <div v-if="createError" class="p-3 rounded-sm bg-red-950/50 border border-red-500/40 text-red-300 text-xs font-mono">
            {{ createError }}
          </div>

          <div class="pt-3 border-t border-slate-800 flex items-center justify-end space-x-3">
            <button
              type="button"
              @click="showModal = false"
              class="px-4 py-2 rounded-sm bg-slate-800 text-slate-300 hover:bg-slate-700 font-mono text-xs"
            >
              Cancelar
            </button>
            <button
              type="submit"
              :disabled="isSubmitting"
              class="px-5 py-2 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs disabled:opacity-50 transition-all shadow-md shadow-cyan-500/20"
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
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
import DeleteProjectButton from '../components/DeleteProjectButton.vue'

const engagements = ref([])
function removeProject(project) {
  engagements.value = engagements.value.filter(item => item.id !== project.id || item.type !== project.type)
}
const isLoading = ref(true)
const currentFilter = ref('all')
const currentCategory = ref('all')
const searchQuery = ref('')

const ctfCategories = [
  { id: 'all', label: 'Todas las Cat.' },
  { id: 'web', label: '🌐 Web' },
  { id: 'crypto', label: '🔐 Crypto' },
  { id: 'pwn', label: '💥 Pwn' },
  { id: 'reverse', label: '🔍 Reversing' },
  { id: 'forensics', label: '🔬 Forensics' },
  { id: 'misc', label: '🧩 Misc' },
  { id: 'osint', label: '👁️ OSINT' },
  { id: 'machine', label: '💻 Máquinas' },
]

function getCategoryBadgeClass(category) {
  switch (category) {
    case 'web': return 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
    case 'crypto': return 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
    case 'pwn': return 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
    case 'reverse': return 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
    case 'forensics': return 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
    case 'osint': return 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
    case 'misc': default: return 'bg-slate-700 text-slate-300 border border-slate-600'
  }
}

const showModal = ref(false)
const isSubmitting = ref(false)
const createError = ref('')
const newForm = ref({
  name: '',
  type: 'engagement',
  domain: '',
  client: '',
  subtype: 'jeopardy',
  category: 'web',
  points: 100,
  difficulty: 'medium',
})

const filteredEngagements = computed(() => {
  return engagements.value.filter(item => {
    const matchesFilter = currentFilter.value === 'all' || item.type === currentFilter.value

    let matchesCategory = true
    if (currentCategory.value !== 'all') {
      if (currentCategory.value === 'machine') {
        matchesCategory = item.type === 'reto' && (item.subtype === 'machine' || !item.subtype)
      } else {
        matchesCategory = item.type === 'reto' && item.category === currentCategory.value
      }
    }

    const query = searchQuery.value.toLowerCase().trim()
    const matchesSearch = !query ||
      item.name.toLowerCase().includes(query) ||
      (item.client_or_platform && item.client_or_platform.toLowerCase().includes(query)) ||
      (item.category && item.category.toLowerCase().includes(query))

    return matchesFilter && matchesCategory && matchesSearch
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
    const created = await api.createEngagement(newForm.value)
    showModal.value = false
    newForm.value = {
      name: '',
      type: 'engagement',
      domain: '',
      client: '',
      subtype: 'jeopardy',
      category: 'web',
      points: 100,
      difficulty: 'medium',
    }
    // Llevar directo al detalle (pestaña Alcance) en vez de volver a la
    // lista: es el siguiente paso natural tras crear un proyecto.
    router.push(`/engagements/${created.type}/${created.id}`)
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
