<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#1b253b] pb-6">
      <div>
        <h1 class="text-2xl font-mono font-bold text-white flex items-center space-x-3">
          <span>⚡ SecLab API Key Vault & Tactical Proxy</span>
          <span class="text-xs px-2 py-0.5 rounded-sm bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono">
            AES-256-GCM
          </span>
          <span class="text-xs px-2 py-0.5 rounded-sm bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-mono">
            FASE 2 ACTIVA
          </span>
        </h1>
        <p class="text-slate-400 text-sm mt-1">
          Almacén cifrado de credenciales de inteligencia, modelos LLM y plataformas con enrutador proxy y failover automático.
        </p>
      </div>

      <div class="flex items-center space-x-3">
        <button
          @click="openAddModal"
          class="px-4 py-2 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-sm transition-all shadow-md shadow-cyan-500/20 flex items-center justify-center space-x-2"
        >
          <span>+</span>
          <span>Configurar Nueva Llave</span>
        </button>
      </div>
    </div>

    <!-- Métricas y Telemetría del Proxy (Fase 2) -->
    <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
      <div class="tactical-card p-3">
        <span class="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Total Peticiones</span>
        <span class="text-xl font-mono font-bold text-white">{{ proxyStats.total_requests || 0 }}</span>
      </div>
      <div class="tactical-card p-3">
        <span class="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Tasa de Éxito</span>
        <span class="text-xl font-mono font-bold text-emerald-400">{{ proxyStats.success_rate_pct || 100 }}%</span>
      </div>
      <div class="tactical-card p-3">
        <span class="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Failover Dinámico</span>
        <span class="text-xl font-mono font-bold text-amber-400">{{ proxyStats.fallback_requests || 0 }}</span>
      </div>
      <div class="tactical-card p-3">
        <span class="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Latencia Media</span>
        <span class="text-xl font-mono font-bold text-cyan-300">{{ proxyStats.avg_latency_ms || 0 }} ms</span>
      </div>
      <div class="tactical-card p-3 col-span-2 sm:col-span-1">
        <span class="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Tokens Consumidos</span>
        <span class="text-xl font-mono font-bold text-purple-400">{{ proxyStats.total_tokens_used || 0 }}</span>
      </div>
    </div>

    <!-- Banner Tools Bridge CLI (Fase 2) -->
    <div class="p-3 rounded-lg bg-cyan-950/30 border border-cyan-500/30 text-xs font-mono text-cyan-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div class="flex items-center space-x-2">
        <span class="text-base">🚀</span>
        <span>
          <strong>Tools Bridge Activo:</strong> Inyecta tus claves directamente en terminal sin tocar disco ejecutando:
          <code class="bg-black/60 px-2 py-0.5 rounded-sm text-cyan-300">pt-vault run &lt;comando&gt;</code>
        </span>
      </div>
      <span class="text-[11px] text-slate-400 whitespace-nowrap">Ej: pt-vault run shodan myinfo</span>
    </div>

    <!-- Pestañas de Servicios -->
    <div class="flex items-center space-x-2 border-b border-slate-800 pb-2 text-xs font-mono">
      <button
        v-for="cat in ['all', 'recon', 'llm', 'platform']"
        :key="cat"
        @click="selectedCategory = cat"
        class="px-3 py-1.5 rounded-sm transition-colors uppercase tracking-wider"
        :class="selectedCategory === cat ? 'bg-cyan-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white bg-slate-800/40'"
      >
        {{ cat === 'all' ? 'Todos' : (cat === 'recon' ? 'Recon & OSINT' : (cat === 'llm' ? 'Modelos AI / LLMs' : 'Plataformas')) }}
      </button>
    </div>

    <!-- Grid de Llaves Configuradas -->
    <div v-if="isLoading" class="text-center py-12 text-slate-400 font-mono text-sm">
      Cargando claves cifradas del Vault...
    </div>

    <div v-else-if="filteredKeys.length === 0" class="text-center py-16 tactical-card space-y-3">
      <div class="text-4xl">🔐</div>
      <p class="text-slate-300 font-mono text-sm">No hay API keys configuradas en esta categoría.</p>
      <button
        @click="openAddModal"
        class="px-4 py-2 rounded-sm bg-cyan-600 text-slate-950 font-bold text-xs font-mono"
      >
        Agregar Clave al Vault
      </button>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      <div
        v-for="k in filteredKeys"
        :key="k.provider"
        class="tactical-card flex flex-col justify-between space-y-4"
      >
        <div>
          <!-- Cabecera de Tarjeta -->
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <span class="text-xl">{{ getProviderIcon(k.provider) }}</span>
              <div>
                <h3 class="font-mono font-bold text-white text-sm">{{ k.label }}</h3>
                <span class="text-[10px] font-mono text-slate-400 uppercase">{{ k.provider }}</span>
              </div>
            </div>

            <!-- Badge de Estado de Salud -->
            <span
              class="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold flex items-center space-x-1"
              :class="getStatusBadgeClass(k.status)"
            >
              <span class="w-1.5 h-1.5 rounded-full" :class="getStatusDotClass(k.status)"></span>
              <span>{{ k.status.toUpperCase() }}</span>
            </span>
          </div>

          <!-- Clave Enmascarada -->
          <div class="mt-4 p-2.5 rounded-sm bg-slate-950/80 border border-slate-800 font-mono text-xs flex items-center justify-between">
            <span class="text-slate-300">{{ k.masked_key }}</span>
            <span class="text-[10px] px-1.5 py-0.2 rounded-sm bg-slate-800 text-slate-400">cifrada</span>
          </div>

          <!-- Mensaje de Estado / Detalles -->
          <p v-if="k.status_message" class="text-[11px] font-mono text-slate-400 mt-2 line-clamp-2">
            {{ k.status_message }}
          </p>

          <div v-if="k.model_name || k.base_url" class="mt-3 text-[11px] font-mono text-slate-500 space-y-0.5">
            <div v-if="k.model_name">Modelo: <span class="text-slate-300">{{ k.model_name }}</span></div>
            <div v-if="k.base_url" class="truncate">URL: <span class="text-slate-300">{{ k.base_url }}</span></div>
          </div>
        </div>

        <!-- Botones de Acción -->
        <div class="pt-3 border-t border-slate-800 flex items-center justify-between text-xs font-mono">
          <div class="flex items-center space-x-2">
            <button
              @click="testKey(k.provider)"
              :disabled="testingProviders[k.provider]"
              class="px-3 py-1.5 rounded-sm bg-slate-800 hover:bg-slate-700 text-cyan-400 border border-slate-700 disabled:opacity-50 transition-colors flex items-center space-x-1"
            >
              <span>⚡</span>
              <span>{{ testingProviders[k.provider] ? 'Probando...' : 'Probar Salud' }}</span>
            </button>

            <button
              @click="openEditModal(k)"
              class="px-2.5 py-1.5 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-cyan-400 border border-slate-700 transition-colors flex items-center space-x-1"
            >
              <span>✏️</span>
              <span>Editar</span>
            </button>
          </div>

          <button
            @click="deleteKeyAction(k.provider)"
            class="text-red-400 hover:text-red-300 hover:underline text-[11px]"
          >
            Eliminar
          </button>
        </div>
      </div>
    </div>

    <!-- Tester del Proxy Unificado con Selector de Perfiles (Fase 2) -->
    <div class="tactical-card bg-linear-to-r from-[#0d1322] to-[#11192e] space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-3 gap-2">
        <div>
          <h2 class="text-sm font-mono font-bold text-white flex items-center space-x-2">
            <span>🤖 Consola Táctica de Inferencia & Failover</span>
          </h2>
          <p class="text-xs text-slate-400">
            Enruta consultas a modelos LLM con failover automático entre proveedores activos.
          </p>
        </div>

        <!-- Selector de Perfiles -->
        <div class="flex items-center space-x-2 text-xs font-mono">
          <span class="text-slate-400">Perfil:</span>
          <div class="flex rounded-sm bg-slate-900 border border-slate-800 p-0.5">
            <button
              v-for="p in [
                { id: 'quick', label: 'Rápido (Flash)' },
                { id: 'deep', label: 'Profundo (Sonnet/4o)' },
                { id: 'local', label: 'Local/Ollama' }
              ]"
              :key="p.id"
              @click="selectedProfile = p.id"
              class="px-2.5 py-1 rounded-sm text-[11px] font-semibold transition-colors"
              :class="selectedProfile === p.id ? 'bg-cyan-500 text-slate-950' : 'text-slate-400 hover:text-white'"
            >
              {{ p.label }}
            </button>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-mono text-slate-300 mb-1">Instrucción / Prompt de Prueba:</label>
          <textarea
            v-model="proxyPromptInput"
            rows="3"
            class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm p-2 text-xs font-mono text-slate-100 focus:outline-hidden"
            placeholder="Analiza brevemente el propósito del principio Evidence-First en auditorías..."
          ></textarea>
          <button
            @click="runProxyTest"
            :disabled="isTestingProxy || !proxyPromptInput.trim()"
            class="mt-2 px-4 py-2 rounded-sm bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-bold text-xs font-mono transition-all shadow-md shadow-cyan-600/20"
          >
            {{ isTestingProxy ? 'Consultando Proxy...' : 'Ejecutar Consulta con Failover' }}
          </button>
        </div>

        <div>
          <label class="block text-xs font-mono text-slate-300 mb-1">Respuesta Upstream del Proxy:</label>
          <div class="h-32 bg-[#050811] border border-slate-800 rounded-sm p-3 text-xs font-mono text-slate-200 overflow-y-auto">
            <span v-if="!proxyResponse && !isTestingProxy" class="text-slate-500">
              Esperando consulta...
            </span>
            <span v-else-if="isTestingProxy" class="text-cyan-400 animate-pulse">
              Enrutando hacia proveedor LLM configurado (con failover automático)...
            </span>
            <div v-else>
              <div class="text-[10px] text-cyan-400 border-b border-slate-800 pb-1 mb-2 font-bold flex justify-between">
                <span>PROVEEDOR: {{ proxyResponse.provider.toUpperCase() }} | MODELO: {{ proxyResponse.model }}</span>
                <span>{{ proxyResponse.latency_ms }} ms</span>
              </div>
              <p class="whitespace-pre-wrap">{{ proxyResponse.content }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Historial de Auditoría de Peticiones Proxy (Fase 2) -->
    <div class="tactical-card space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 class="text-sm font-mono font-bold text-white uppercase tracking-wider flex items-center space-x-2">
          <span>📜 Bitácora de Peticiones del Proxy</span>
        </h3>
        <button
          @click="loadProxyHistory"
          class="text-xs font-mono text-cyan-400 hover:underline"
        >
          Refrescar Historial
        </button>
      </div>

      <div v-if="proxyHistory.length === 0" class="text-center py-6 text-slate-500 font-mono text-xs">
        No hay registros recientes en la bitácora de auditoría del Proxy.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-left font-mono text-xs text-slate-300">
          <thead class="border-b border-slate-800 text-[10px] text-slate-500 uppercase tracking-wider">
            <tr>
              <th class="py-2">Timestamp</th>
              <th class="py-2">Proveedor</th>
              <th class="py-2">Modelo</th>
              <th class="py-2">Estado</th>
              <th class="py-2">Latencia</th>
              <th class="py-2 text-right">Tokens</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            <tr v-for="h in proxyHistory" :key="h.id" class="hover:bg-slate-800/20">
              <td class="py-2 text-slate-400">{{ h.created_at ? h.created_at.slice(11, 19) : '-' }}</td>
              <td class="py-2 font-bold uppercase text-slate-200">{{ h.provider }}</td>
              <td class="py-2 text-slate-400 truncate max-w-[150px]">{{ h.model }}</td>
              <td class="py-2">
                <span
                  class="px-1.5 py-0.5 rounded-sm text-[10px] font-bold"
                  :class="h.status === 'success' ? 'bg-emerald-500/10 text-emerald-400' : (h.status === 'fallback' ? 'bg-amber-500/10 text-amber-400' : 'bg-red-500/10 text-red-400')"
                >
                  {{ h.status }}
                </span>
              </td>
              <td class="py-2 text-cyan-300">{{ h.latency_ms }} ms</td>
              <td class="py-2 text-right text-purple-300 font-bold">{{ h.tokens_used }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Modal Agregar / Configurar / Editar API Key -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 overflow-y-auto"
    >
      <div class="bg-[#0d1322] border border-cyan-500/40 rounded-lg max-w-lg w-full p-6 shadow-2xl space-y-4 my-8">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 class="text-base font-mono font-bold text-white flex items-center space-x-2">
            <span>{{ isEditing ? '✏️ Editar Configuración: ' + (keyForm.label || keyForm.provider) : '🔑 Registrar API Key en Vault SecLab' }}</span>
          </h2>
          <button @click="showModal = false" class="text-slate-400 hover:text-white font-mono text-lg">&times;</button>
        </div>

        <form @submit.prevent="submitKey" class="space-y-4">
          <div>
            <label class="block text-xs font-mono text-slate-300 mb-1">
              Proveedor / Servicio:
              <span v-if="isEditing" class="text-slate-500 font-normal ml-1">(Identificador de proveedor fijo)</span>
            </label>
            <select
              v-model="keyForm.provider"
              @change="onProviderSelect"
              :disabled="isEditing"
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-2 text-xs font-mono text-slate-100 focus:outline-hidden disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <optgroup label="Reconocimiento & OSINT">
                <option value="shodan">Shodan (Search & Host API)</option>
                <option value="censys">Censys (Search API)</option>
                <option value="virustotal">VirusTotal (v3 API)</option>
                <option value="chaos">ProjectDiscovery / Chaos</option>
              </optgroup>
              <optgroup label="Modelos de Lenguaje (AI)">
                <option value="openrouter">OpenRouter (100+ Modelos: Claude, DeepSeek, Llama)</option>
                <option value="openai">OpenAI (GPT-4o / GPT-4o-mini)</option>
                <option value="anthropic">Anthropic (Claude 3.5 Sonnet)</option>
                <option value="gemini">Google Gemini (Gemini 2.0 Flash)</option>
                <option value="custom_llm">Endpoint Local / Ollama (OpenAI Compatible)</option>
              </optgroup>
              <optgroup label="Plataformas de Laboratorio">
                <option value="hackthebox">HackTheBox API Token</option>
                <option value="tryhackme">TryHackMe API</option>
              </optgroup>
            </select>
          </div>

          <div>
            <label class="block text-xs font-mono text-slate-300 mb-1">Etiqueta Identificadora:</label>
            <input
              v-model="keyForm.label"
              type="text"
              required
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
            />
          </div>

          <div>
            <label class="block text-xs font-mono text-slate-300 mb-1">
              API Key / Token Secreto:
              <span v-if="isEditing" class="text-slate-400 font-normal ml-1">(Opcional al editar)</span>
            </label>
            <input
              v-model="keyForm.api_key"
              type="password"
              :required="!isEditing"
              :placeholder="isEditing ? '(Dejar vacío para conservar clave actual cifrada)' : 'sk-..., token_..., key_...'"
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
            />
            <p class="text-[10px] text-slate-500 mt-1 font-mono">
              {{ isEditing ? 'Si ingresas un nuevo valor, se cifrará con AES-256-GCM reemplazando la clave previa.' : 'Se cifra localmente con AES-256-GCM antes de guardarse en SQLite.' }}
            </p>
          </div>

          <div v-if="keyForm.provider === 'openrouter' || keyForm.provider === 'custom_llm' || keyForm.service_type === 'llm' || isEditing" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">Base URL (Endpoint):</label>
              <input
                v-model="keyForm.base_url"
                type="text"
                :placeholder="keyForm.provider === 'openrouter' ? 'https://openrouter.ai/api/v1' : (keyForm.provider === 'custom_llm' ? 'http://localhost:11434/v1' : 'https://api.openai.com/v1')"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
              />
              <p class="text-[10px] text-slate-500 mt-1 font-mono">
                Se limpian espacios y se normaliza el esquema http(s) automáticamente.
              </p>
            </div>
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">Modelo Inicial / Predeterminado:</label>
              <div v-if="formIsOpenRouter" class="space-y-1.5">
                <select
                  @change="keyForm.model_name = $event.target.value"
                  :value="keyForm.model_name"
                  class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-2 py-1 text-xs font-mono text-slate-100 focus:outline-hidden"
                >
                  <option value="">Elegir modelo base</option>
                  <option v-for="model in filteredFormModels" :key="model.id" :value="model.id">{{ model.name }} — {{ model.id }}</option>
                  <option v-if="keyForm.model_name && !filteredFormModels.some(m => m.id === keyForm.model_name)" :value="keyForm.model_name">{{ keyForm.model_name }} (selección actual)</option>
                </select>
                <input v-model="formModelSearch" aria-label="Buscar modelos" placeholder="Buscar por nombre o ID" class="w-full bg-[#070b14] border border-slate-700 px-2 py-1 text-xs" />
                <button type="button" @click="loadFormModels" :disabled="formModelsLoading" class="text-xs text-cyan-300">{{ formModelsLoading ? 'Consultando…' : 'Consultar modelos con esta clave' }}</button>
                <p class="text-xs text-slate-400">{{ formModels.length }} modelos. La consulta no guarda la clave. El modelo base se guarda al confirmar.</p>
                <p v-if="formModelsError" role="alert" class="text-xs text-red-400">{{ formModelsError }}</p>
              </div>
              <input
                v-else
                v-model="keyForm.model_name"
                type="text"
                placeholder="llama3:latest, mistral, gpt-4o"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
              />
            </div>
          </div>

          <div v-if="isEditing" class="flex items-center space-x-2 pt-1">
            <input
              id="key_is_active"
              v-model="keyForm.is_active"
              type="checkbox"
              class="rounded-sm bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0 focus:ring-offset-0"
            />
            <label for="key_is_active" class="text-xs font-mono text-slate-300 cursor-pointer">
              Llave Activa en el Vault (Disponible para inferencia y herramientas)
            </label>
          </div>

          <div class="pt-3 border-t border-slate-800 flex items-center justify-end space-x-3">
            <button
              type="button"
              @click="showModal = false"
              class="px-4 py-2 rounded-sm bg-slate-800 text-slate-300 text-xs font-mono hover:bg-slate-700 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              class="px-5 py-2 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs font-mono shadow-md shadow-cyan-500/20 transition-all"
            >
              {{ isEditing ? 'Actualizar Configuración' : 'Guardar Llave Cifrada' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '../api'

const keys = ref([])
const isLoading = ref(true)
const selectedCategory = ref('all')
const testingProviders = ref({})

// Fase 2: Stats & History
const proxyStats = ref({})
const proxyHistory = ref([])
const selectedProfile = ref('quick')

const showModal = ref(false)
const isEditing = ref(false)
const editingProvider = ref(null)
const keyForm = ref({
  provider: 'shodan',
  label: 'Shodan Search API',
  service_type: 'recon',
  api_key: '',
  base_url: '',
  model_name: '',
  is_active: true,
})

const formModels = ref([])
const formModelSearch = ref('')
const formModelsLoading = ref(false)
const formModelsError = ref('')
const formIsOpenRouter = computed(() => {
  if (keyForm.value.provider === 'openrouter') return true
  try { return keyForm.value.provider === 'custom_llm' && ['openrouter.ai', 'eu.openrouter.ai'].includes(new URL(keyForm.value.base_url.trim().includes('://') ? keyForm.value.base_url.trim() : `https://${keyForm.value.base_url.trim()}`).hostname) } catch { return false }
})
const filteredFormModels = computed(() => formModels.value.filter(m => `${m.name} ${m.id}`.toLowerCase().includes(formModelSearch.value.toLowerCase())))
let modelRequest = 0
watch(() => [keyForm.value.provider, keyForm.value.api_key, keyForm.value.base_url], () => {
  modelRequest++
  formModels.value = []
  formModelsError.value = ''
  formModelsLoading.value = false
})
async function loadFormModels() {
  const currentRequest = ++modelRequest
  formModelsLoading.value = true
  formModelsError.value = ''
  try {
    const catalog = await api.previewProviderModels({ provider: keyForm.value.provider, base_url: keyForm.value.base_url || null, api_key: keyForm.value.api_key.trim() || null })
    if (currentRequest !== modelRequest) return
    formModels.value = catalog.models
    if (!formModels.value.some(m => m.id === keyForm.value.model_name)) keyForm.value.model_name = catalog.default_model || ''
  } catch (err) { if (currentRequest === modelRequest) formModelsError.value = err.message }
  finally { if (currentRequest === modelRequest) formModelsLoading.value = false }
}

// Proxy Test
const proxyPromptInput = ref('Resume en 2 viñetas los beneficios del aislamiento con Tailscale en un laboratorio de pentesting.')
const isTestingProxy = ref(false)
const proxyResponse = ref(null)

const filteredKeys = computed(() => {
  return keys.value.filter(k => {
    return selectedCategory.value === 'all' || k.service_type === selectedCategory.value
  })
})

function getProviderIcon(provider) {
  switch (provider) {
    case 'shodan': return '🔍'
    case 'censys': return '🌐'
    case 'virustotal': return '🦠'
    case 'chaos': return '⚡'
    case 'openrouter': return '🔀'
    case 'openai': return '🤖'
    case 'anthropic': return '🧠'
    case 'gemini': return '✨'
    case 'custom_llm': return '💻'
    case 'hackthebox': return '🟩'
    case 'tryhackme': return '🟥'
    default: return '🔑'
  }
}

function getStatusBadgeClass(status) {
  switch (status) {
    case 'online': return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
    case 'rate_limited': return 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
    case 'error': return 'bg-red-500/10 text-red-400 border border-red-500/30'
    default: return 'bg-slate-800 text-slate-400 border border-slate-700'
  }
}

function getStatusDotClass(status) {
  switch (status) {
    case 'online': return 'bg-emerald-400'
    case 'rate_limited': return 'bg-amber-400'
    case 'error': return 'bg-red-400'
    default: return 'bg-slate-500'
  }
}

function onProviderSelect() {
  const p = keyForm.value.provider
  if (['shodan', 'censys', 'virustotal', 'chaos'].includes(p)) {
    keyForm.value.service_type = 'recon'
  } else if (['openrouter', 'openai', 'anthropic', 'gemini', 'custom_llm'].includes(p)) {
    keyForm.value.service_type = 'llm'
  } else {
    keyForm.value.service_type = 'platform'
  }

  const defaultLabels = {
    shodan: 'Shodan API Key',
    censys: 'Censys Search Token',
    virustotal: 'VirusTotal v3 Key',
    chaos: 'ProjectDiscovery Chaos Key',
    openrouter: 'OpenRouter API Key',
    openai: 'OpenAI API Key',
    anthropic: 'Anthropic Claude Key',
    gemini: 'Google Gemini Key',
    custom_llm: 'Endpoint Local / Ollama',
    hackthebox: 'HackTheBox Token',
    tryhackme: 'TryHackMe Key',
  }
  keyForm.value.label = defaultLabels[p] || p

  if (p === 'openrouter') {
    keyForm.value.base_url = 'https://openrouter.ai/api/v1'
    keyForm.value.model_name = ''
  }
}

function openAddModal() {
  isEditing.value = false
  editingProvider.value = null
  keyForm.value = {
    provider: 'shodan',
    label: 'Shodan API Key',
    service_type: 'recon',
    api_key: '',
    base_url: '',
    model_name: '',
    is_active: true,
  }
  showModal.value = true
}

function openEditModal(k) {
  isEditing.value = true
  editingProvider.value = k.provider
  keyForm.value = {
    provider: k.provider,
    label: k.label || '',
    service_type: k.service_type || 'llm',
    api_key: '',
    base_url: k.base_url || '',
    model_name: k.model_name || '',
    is_active: k.is_active ?? true,
  }
  showModal.value = true
}

async function loadKeys() {
  isLoading.value = true
  try {
    keys.value = await api.getVaultKeys()
  } catch (err) {
    console.error('Error al cargar llaves del Vault:', err)
  } finally {
    isLoading.value = false
  }
}

async function loadProxyStats() {
  try {
    proxyStats.value = await api.getProxyStats()
  } catch (err) {
    console.error('Error al cargar stats:', err)
  }
}

async function loadProxyHistory() {
  try {
    proxyHistory.value = await api.getProxyHistory(15)
  } catch (err) {
    console.error('Error al cargar historial:', err)
  }
}

async function submitKey() {
  try {
    if (formIsOpenRouter.value && !formModels.value.some(m => m.id === keyForm.value.model_name)) {
      throw new Error('Consulta el catálogo y elige un modelo base disponible antes de guardar')
    }
    if (isEditing.value && editingProvider.value) {
      const payload = {
        label: keyForm.value.label,
        base_url: keyForm.value.base_url,
        model_name: keyForm.value.model_name,
        is_active: keyForm.value.is_active,
      }
      if (keyForm.value.api_key && keyForm.value.api_key.trim()) {
        payload.api_key = keyForm.value.api_key.trim()
      }
      await api.updateVaultKey(editingProvider.value, payload)
    } else {
      await api.upsertVaultKey(keyForm.value)
    }
    showModal.value = false
    await loadKeys()
  } catch (err) {
    alert('Error al guardar llave: ' + err.message)
  }
}

async function testKey(provider) {
  testingProviders.value[provider] = true
  try {
    const res = await api.testVaultKey(provider)
    await loadKeys()
    alert(`Resultado [${res.provider}]: ${res.status.toUpperCase()}\n${res.message}`)
  } catch (err) {
    alert('Error al probar conexión: ' + err.message)
  } finally {
    testingProviders.value[provider] = false
  }
}

async function deleteKeyAction(provider) {
  if (!confirm(`¿Eliminar la llave para ${provider} del Vault?`)) return
  try {
    await api.deleteVaultKey(provider)
    await loadKeys()
  } catch (err) {
    alert(err.message)
  }
}

async function runProxyTest() {
  if (!proxyPromptInput.value.trim()) return
  isTestingProxy.value = true
  proxyResponse.value = null
  try {
    const res = await api.proxyChat(
      [{ role: 'user', content: proxyPromptInput.value.trim() }],
      null,
      null,
      selectedProfile.value
    )
    proxyResponse.value = res
    await Promise.all([loadProxyStats(), loadProxyHistory()])
  } catch (err) {
    alert('Error en consulta proxy: ' + err.message)
  } finally {
    isTestingProxy.value = false
  }
}

onMounted(() => {
  loadKeys()
  loadProxyStats()
  loadProxyHistory()
})
</script>
