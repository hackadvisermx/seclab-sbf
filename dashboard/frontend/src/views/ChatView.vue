<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#1b253b] pb-6">
      <div>
        <h1 class="text-2xl font-mono font-bold text-white flex items-center space-x-3">
          <span>💬 Chat IA Táctico</span>
          <span class="text-xs px-2 py-0.5 rounded-sm bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 font-mono">
            OPENROUTER & MODEL HUB
          </span>
          <span
            v-if="hasActiveKey"
            class="text-xs px-2 py-0.5 rounded-sm bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono flex items-center space-x-1"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>VAULT ONLINE</span>
          </span>
        </h1>
        <p class="text-slate-400 text-sm mt-1">
          Interacción directa con modelos de vanguardia vía SecLab Tactical Proxy. Selecciona cualquier modelo de OpenRouter o proveedores del Vault.
        </p>
      </div>

      <div class="flex items-center space-x-2">
        <button
          @click="clearChat"
          type="button"
          class="px-3 py-1.5 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-mono transition-colors flex items-center space-x-1.5"
          title="Reiniciar conversación"
        >
          <span>🗑️</span>
          <span>Limpiar</span>
        </button>
        <button
          @click="exportChat"
          type="button"
          class="px-3 py-1.5 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-mono transition-colors flex items-center space-x-1.5"
          title="Descargar chat como Markdown"
        >
          <span>📥</span>
          <span>Exportar</span>
        </button>
        <router-link
          to="/vault"
          class="px-3 py-1.5 rounded-sm bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs font-mono transition-colors flex items-center space-x-1.5"
          title="Gestionar claves en el API Vault"
        >
          <span>🔑</span>
          <span>API Vault</span>
        </router-link>
      </div>
    </div>

    <!-- Banner si no hay claves de LLM activas en el Vault -->
    <div
      v-if="!isLoadingKeys && !hasActiveKey"
      class="p-4 rounded-lg bg-amber-950/40 border border-amber-500/40 text-amber-200 text-xs font-mono flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-md"
    >
      <div class="flex items-center space-x-3">
        <span class="text-2xl">⚠️</span>
        <div>
          <strong class="text-amber-300">No se detectó ninguna API Key activa para LLMs en el Vault:</strong>
          <p class="text-amber-200/80 mt-0.5">
            Para consultar modelos de OpenRouter, OpenAI, Anthropic o Gemini, agrega tu clave en el almacén cifrado.
          </p>
        </div>
      </div>
      <router-link
        to="/vault"
        class="px-3 py-1.5 rounded-sm bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold font-mono text-xs whitespace-nowrap shadow-sm text-center"
      >
        Configurar en Vault →
      </router-link>
    </div>

    <!-- Barra de Configuración de Modelo y Parámetros -->
    <div class="tactical-card p-4 space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs font-mono">
        <!-- Selector de Proveedor -->
        <div>
          <label class="block text-slate-400 text-[11px] uppercase font-semibold mb-1">
            Proveedor:
          </label>
          <select
            v-model="selectedProvider"
            @change="onProviderChange"
            class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-2 text-cyan-300 focus:outline-hidden"
          >
            <option value="openrouter">🔀 OpenRouter (100+ Modelos)</option>
            <option value="openai">🤖 OpenAI</option>
            <option value="anthropic">🧠 Anthropic Claude</option>
            <option value="gemini">✨ Google Gemini</option>
            <option value="custom_llm">💻 Local / Ollama</option>
          </select>
        </div>

        <!-- Selector de Modelo -->
        <div class="md:col-span-2">
          <label class="block text-slate-400 text-[11px] uppercase font-semibold mb-1 flex items-center justify-between">
            <span>Modelo:</span>
            <span v-if="selectedProvider === 'openrouter'" class="text-[10px] text-cyan-400 font-normal">
              Directo OpenRouter Hub
            </span>
          </label>
          <div class="flex gap-2">
            <select
              v-if="selectedProvider === 'openrouter'"
              v-model="selectedOpenRouterPreset"
              @change="onOpenRouterPresetChange"
              class="flex-1 min-w-0 bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-2 text-white focus:outline-hidden"
            >
              <option value="">Elegir modelo</option>
              <option v-for="model in filteredModels" :key="model.id" :value="model.id">{{ model.name }} — {{ model.id }}</option>
              <option v-if="selectedOpenRouterPreset && selectedOpenRouterPreset !== 'custom' && !filteredModels.some(m => m.id === selectedOpenRouterPreset)" :value="selectedOpenRouterPreset">{{ selectedOpenRouterPreset }} (selección actual)</option>
              <option value="custom">✏️ Personalizado (Escribir Slug)</option>
            </select>

            <!-- Input modelo para otros proveedores o custom -->
            <input
              v-if="selectedProvider !== 'openrouter' || selectedOpenRouterPreset === 'custom'"
              v-model="customModelName"
              type="text"
              :placeholder="selectedProvider === 'openrouter' ? 'ej. deepseek/deepseek-r1' : 'ej. gpt-4o, claude-3-5-sonnet'"
              class="flex-1 min-w-0 bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-2 text-white focus:outline-hidden"
            />
          </div>
          <div v-if="selectedProvider === 'openrouter'" class="mt-2 space-y-1">
            <input v-model="modelSearch" aria-label="Buscar modelos" placeholder="Buscar por nombre o ID" class="w-full bg-[#070b14] border border-slate-700 px-2 py-1 text-sm" />
            <button type="button" @click="loadModels" :disabled="modelsLoading" class="text-xs text-cyan-300">{{ modelsLoading ? 'Consultando…' : 'Actualizar catálogo' }}</button>
            <p class="text-xs text-slate-400">{{ availableModels.length }} modelos de tu cuenta. El saldo, los límites y la disponibilidad se comprueban al consultar.</p>
            <p v-if="modelsError" role="alert" class="text-xs text-red-400">{{ modelsError }}</p>
          </div>
        </div>

        <!-- Selector de Rol / Persona Táctica -->
        <div>
          <label class="block text-slate-400 text-[11px] uppercase font-semibold mb-1">
            Rol Táctico:
          </label>
          <select
            v-model="selectedPersona"
            class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-2 text-slate-200 focus:outline-hidden"
          >
            <option value="red-team">🎯 Red Team & Pentesting</option>
            <option value="triage">🛡️ Triaje & Evidence-First</option>
            <option value="api-logic">🔌 Lógica de Negocio & APIs</option>
            <option value="exploit-dev">⚡ Desarrollo de Exploits / PoC</option>
            <option value="general">🤖 Asistente Táctico General</option>
          </select>
        </div>
      </div>

      <!-- Barra de chips rápidos y temperatura -->
      <div class="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800 text-[11px] font-mono">
        <div class="flex items-center space-x-2">
          <span class="text-slate-400">Modelo Activo:</span>
          <span class="px-2 py-0.5 rounded-sm bg-cyan-950/80 border border-cyan-500/30 text-cyan-300 font-bold">
            {{ effectiveModelDisplay }}
          </span>
        </div>

        <div class="flex items-center space-x-3">
          <label class="text-slate-400 flex items-center space-x-1.5">
            <span>Temperatura:</span>
            <span class="font-bold text-cyan-400">{{ temperature }}</span>
          </label>
          <input
            v-model.number="temperature"
            type="range"
            min="0.0"
            max="1.0"
            step="0.1"
            class="w-24 accent-cyan-400 cursor-pointer"
          />
          <button
            @click="setAsDefaultAuditModel"
            type="button"
            class="px-2.5 py-1 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors cursor-pointer"
            title="Establecer este modelo como el inicial para auditorías futuras"
          >
            ⭐ Usar por Defecto en Auditorías
          </button>
        </div>
      </div>
    </div>

    <!-- Ventana Principal de Conversación -->
    <div class="tactical-card p-4 space-y-4 flex flex-col h-[560px]">
      <div
        ref="chatContainer"
        class="flex-1 bg-[#050811] border border-slate-800 rounded-lg p-4 overflow-y-auto space-y-4 font-mono text-xs"
      >
        <!-- Estado Vacío: Bienvenida & Prompts Rápidos -->
        <div v-if="messages.length === 0" class="text-center py-16 text-slate-400 space-y-4 max-w-2xl mx-auto">
          <div class="w-14 h-14 rounded-full bg-[#0d1322] border border-cyan-500/40 mx-auto flex items-center justify-center text-2xl text-cyan-400 shadow-lg shadow-cyan-500/10">
            💬
          </div>
          <div>
            <h3 class="text-white font-bold text-sm">SecLab Tactical Chat & OpenRouter Hub</h3>
            <p class="text-slate-400 text-xs mt-1">
              Consulta directamente modelos sin intermediarios para análisis de objetivos, validación de hipótesis o generación de PoCs técnicas.
            </p>
          </div>

          <!-- Sugerencias de Inicio Rápido -->
          <div class="text-left pt-2 space-y-2">
            <span class="text-[10px] text-slate-500 uppercase tracking-wider block font-bold">Consultas Frecuentes:</span>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <button
                v-for="(prompt, idx) in quickPrompts"
                :key="idx"
                @click="sendQuickPrompt(prompt)"
                class="p-2.5 rounded-sm bg-[#0a0f1d] border border-slate-800 hover:border-cyan-500/40 text-slate-300 hover:text-cyan-300 text-left transition-all"
              >
                {{ prompt }}
              </button>
            </div>
          </div>
        </div>

        <!-- Lista de Mensajes -->
        <div
          v-for="(m, i) in messages"
          :key="i"
          class="flex flex-col space-y-1.5"
          :class="m.role === 'user' ? 'items-end' : 'items-start'"
        >
          <!-- Metadata Cabecera del Mensaje -->
          <div class="flex items-center space-x-2 text-[10px] text-slate-500 font-bold uppercase">
            <span>{{ m.role === 'user' ? 'OPERADOR' : (m.role === 'system' ? 'SISTEMA' : 'MODELO') }}</span>
            <span v-if="m.model" class="text-cyan-400 font-mono">({{ m.model }})</span>
            <span v-if="m.provider" class="text-slate-400 font-mono">[{{ m.provider }}]</span>
            <span v-if="m.latency_ms" class="text-slate-500">⚡ {{ m.latency_ms }} ms</span>
            <span v-if="m.tokens" class="text-slate-500">🪙 {{ m.tokens }} tokens</span>
            <span v-if="m.time" class="text-slate-600">{{ m.time }}</span>
          </div>

          <!-- Burbuja de Contenido -->
          <div
            class="max-w-[85%] rounded-lg p-3 text-xs leading-relaxed transition-all relative group"
            :class="m.role === 'user'
              ? 'bg-cyan-950/60 border border-cyan-500/40 text-cyan-100 shadow-sm'
              : (m.role === 'error'
                  ? 'bg-red-950/50 border border-red-500/40 text-red-200'
                  : 'bg-[#0d1424] border border-slate-800 text-slate-200 shadow-sm')"
          >
            <!-- Formato pre-wrap para preservar código y viñetas -->
            <div class="whitespace-pre-wrap font-mono">{{ m.content }}</div>

            <!-- Botón Copiar Respuesta -->
            <button
              v-if="m.role === 'assistant'"
              @click="copyMessageContent(m.content, i)"
              type="button"
              class="mt-2 text-[10px] text-slate-400 hover:text-cyan-300 border border-slate-700/60 px-2 py-0.5 rounded-sm bg-black/40 flex items-center space-x-1 cursor-pointer"
            >
              <span v-if="copiedIndex === i" class="text-emerald-400">✓ Copiado al portapapeles</span>
              <span v-else>📋 Copiar Respuesta</span>
            </button>
          </div>
        </div>

        <!-- Indicador de Espera / Pensando -->
        <div v-if="isThinking" class="flex flex-col items-start space-y-1 text-xs">
          <div class="flex items-center space-x-2 text-[10px] text-slate-500 font-bold uppercase">
            <span>MODELO</span>
            <span class="text-cyan-400">({{ effectiveModelDisplay }})</span>
          </div>
          <div class="bg-[#0d1424] border border-cyan-500/30 rounded-lg p-3 text-cyan-300 flex items-center space-x-2">
            <span class="animate-spin text-sm">⚡</span>
            <span>Generando respuesta vía Tactical Proxy...</span>
          </div>
        </div>
      </div>

      <!-- Barra de Envío de Mensaje -->
      <form @submit.prevent="sendMessage" class="space-y-2">
        <div class="flex items-end gap-2">
          <textarea
            v-model="inputMessage"
            @keydown.enter.exact.prevent="sendMessage"
            rows="2"
            placeholder="Escribe tu consulta al modelo... (Enter para enviar, Shift+Enter para salto de línea)"
            class="flex-1 min-w-0 bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-lg px-4 py-2.5 text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-hidden resize-none"
            :disabled="isThinking"
          ></textarea>
          <button
            type="submit"
            :disabled="isThinking || !inputMessage.trim()"
            class="px-5 py-3 rounded-lg bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold text-xs font-mono transition-all shadow-md shadow-cyan-500/20 whitespace-nowrap cursor-pointer"
          >
            <span>Enviar ↵</span>
          </button>
        </div>
        <div class="flex items-center justify-between text-[10px] font-mono text-slate-500 px-1">
          <span>Presiona Enter para enviar. Shift + Enter para nueva línea.</span>
          <span v-if="notificationMsg" class="text-emerald-400 font-semibold">{{ notificationMsg }}</span>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { api } from '../api'

const messages = ref([])
const inputMessage = ref('')
const isThinking = ref(false)
const chatContainer = ref(null)
const copiedIndex = ref(null)
const notificationMsg = ref('')

const selectedProvider = ref('openrouter')
const selectedOpenRouterPreset = ref('')
const customModelName = ref('')
const selectedPersona = ref('red-team')
const temperature = ref(0.2)

const vaultKeys = ref([])
const isLoadingKeys = ref(true)

const availableModels = ref([])
const modelSearch = ref('')
const modelsLoading = ref(false)
const modelsError = ref('')
const filteredModels = computed(() => availableModels.value.filter(m => `${m.name} ${m.id}`.toLowerCase().includes(modelSearch.value.toLowerCase())))
const openRouterKey = computed(() => vaultKeys.value.find(k => k.provider === 'openrouter' && k.is_active) || vaultKeys.value.find(k => k.provider === 'custom_llm' && k.is_active && isOpenRouter(k.base_url)))
function isOpenRouter(url) {
  try { return ['openrouter.ai', 'eu.openrouter.ai'].includes(new URL(url?.trim().includes('://') ? url.trim() : `https://${url?.trim()}`).hostname) } catch { return false }
}
async function loadModels() {
  modelsLoading.value = true
  modelsError.value = ''
  try {
    const catalog = await api.getProviderModels(openRouterKey.value?.provider || 'openrouter')
    availableModels.value = catalog.models
    const preferred = catalog.default_model
    if (!availableModels.value.some(m => m.id === selectedOpenRouterPreset.value)) {
      selectedOpenRouterPreset.value = availableModels.value.some(m => m.id === preferred) ? preferred : ''
    }
  } catch (err) {
    availableModels.value = []
    modelsError.value = err.message
  } finally { modelsLoading.value = false }
}

const quickPrompts = [
  '¿Cómo validar un IDOR con control negativo según Evidence-First?',
  'Genera un script en Python para extracción de endpoints desde un sitemap y robots.txt.',
  'Explica la diferencia técnica entre BFLA (Function Level) y BOLA (Object Level).',
  'Ayuda a redactar el impacto de negocio para un hallazgo de SSRF en una pasarela de pago.',
]

const PERSONA_PROMPTS = {
  'red-team': 'Eres un Operador Red Team de élite en SecLab-SBF. Proporciona explicaciones técnicas, precisas, reproducibles y orientadas a la acción sin palabrería.',
  'triage': 'Eres un Triager y Gatekeeper Evidence-First. Tu enfoque es verificar la reproducibilidad, evaluar falsos positivos, clasificar impacto CVSS y exigir evidencia tangible.',
  'api-logic': 'Eres un Auditor de Lógica de Negocio y Seguridad de APIs (OWASP API Top 10). Analiza controles de flujo, invariantes de estado y control de acceso.',
  'exploit-dev': 'Eres un Investigador de Seguridad y Desarrollador de Exploits. Diseña pruebas de concepto (PoCs) seguras, no destructivas y acotadas para demostrar impacto.',
  'general': 'Eres el Asistente Táctico de Ciberseguridad de SecLab-SBF. Responde de forma clara y técnica utilizando mejores prácticas de la industria.',
}

const effectiveModel = computed(() => {
  if (selectedProvider.value === 'openrouter') {
    if (selectedOpenRouterPreset.value === 'custom') {
      return customModelName.value.trim()
    }
    return selectedOpenRouterPreset.value
  }
  return customModelName.value.trim() || (selectedProvider.value === 'openai' ? 'gpt-4o' : 'claude-3-5-sonnet')
})

const effectiveModelDisplay = computed(() => {
  return `${selectedProvider.value}:${effectiveModel.value}`
})

const hasActiveKey = computed(() => {
  return selectedProvider.value === 'openrouter' ? !!openRouterKey.value : vaultKeys.value.some(k => k.provider === selectedProvider.value && k.service_type === 'llm' && k.is_active)
})

function onProviderChange() {
  if (selectedProvider.value === 'custom_llm' && openRouterKey.value?.provider === 'custom_llm') selectedProvider.value = 'openrouter'
  if (selectedProvider.value === 'openrouter') {
    selectedOpenRouterPreset.value = openRouterKey.value?.model_name || ''
    loadModels()
  } else if (selectedProvider.value === 'openai') {
    customModelName.value = 'gpt-4o'
  } else if (selectedProvider.value === 'anthropic') {
    customModelName.value = 'claude-3-5-sonnet-20241022'
  } else if (selectedProvider.value === 'gemini') {
    customModelName.value = 'gemini-2.0-flash'
  } else if (selectedProvider.value === 'custom_llm') {
    customModelName.value = 'local-model'
  }
  savePreferences()
}

function onOpenRouterPresetChange() {
  if (selectedOpenRouterPreset.value !== 'custom') {
    customModelName.value = ''
  }
  savePreferences()
}

function setAsDefaultAuditModel() {
  if (typeof localStorage !== 'undefined') {
    const modelToSet = selectedProvider.value === 'openrouter'
      ? `openrouter:${effectiveModel.value}`
      : `${selectedProvider.value}:${effectiveModel.value}`
    localStorage.setItem('seclab_default_audit_model', modelToSet)
    notificationMsg.value = `✓ Modelo guardado como predeterminado para auditorías (${modelToSet})`
    setTimeout(() => { notificationMsg.value = '' }, 3000)
  }
}

function savePreferences() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('seclab_chat_provider', selectedProvider.value)
    localStorage.setItem('seclab_chat_openrouter_preset', selectedOpenRouterPreset.value)
    localStorage.setItem('seclab_chat_custom_model', customModelName.value)
    localStorage.setItem('seclab_chat_persona', selectedPersona.value)
  }
}

function loadPreferences() {
  if (typeof localStorage !== 'undefined') {
    const prov = localStorage.getItem('seclab_chat_provider')
    if (prov) selectedProvider.value = prov

    const preset = localStorage.getItem('seclab_chat_openrouter_preset')
    if (preset) selectedOpenRouterPreset.value = preset

    const custom = localStorage.getItem('seclab_chat_custom_model')
    if (custom) customModelName.value = custom

    const persona = localStorage.getItem('seclab_chat_persona')
    if (persona) selectedPersona.value = persona

    const savedHistory = localStorage.getItem('seclab_tactical_chat_history')
    if (savedHistory) {
      try {
        messages.value = JSON.parse(savedHistory)
      } catch {
        // ignore
      }
    }
  }
}

function persistChat() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('seclab_tactical_chat_history', JSON.stringify(messages.value))
  }
}

function clearChat() {
  messages.value = []
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('seclab_tactical_chat_history')
  }
}

function exportChat() {
  if (messages.value.length === 0) return
  const lines = ['# SecLab Tactical Chat Export', `Fecha: ${new Date().toISOString()}`, `Modelo: ${effectiveModelDisplay.value}\n`]
  for (const m of messages.value) {
    const role = m.role === 'user' ? 'Operador' : 'Asistente IA'
    lines.push(`### [${role}] - ${m.time || ''}`)
    lines.push(m.content)
    lines.push('\n---\n')
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `seclab-chat-${Date.now()}.md`
  a.click()
  URL.revokeObjectURL(url)
}

async function copyMessageContent(content, index) {
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(content)
      copiedIndex.value = index
      setTimeout(() => { copiedIndex.value = null }, 2000)
    }
  } catch {
    // ignore
  }
}

function sendQuickPrompt(prompt) {
  inputMessage.value = prompt
  sendMessage()
}

async function sendMessage() {
  if (!inputMessage.value.trim() || isThinking.value) return
  if (!hasActiveKey.value || !effectiveModel.value) {
    notificationMsg.value = 'Configura una clave activa y elige un modelo antes de enviar.'
    return
  }

  isThinking.value = true
  const userText = inputMessage.value.trim()
  inputMessage.value = ''
  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  messages.value.push({
    role: 'user',
    content: userText,
    time: now,
  })

  persistChat()
  await scrollToBottom()

  try {
    // Construir historial de mensajes incluyendo instrucción de sistema
    const payloadMessages = [
      { role: 'system', content: PERSONA_PROMPTS[selectedPersona.value] || PERSONA_PROMPTS['general'] }
    ]

    for (const m of messages.value) {
      if (m.role === 'user' || m.role === 'assistant') {
        payloadMessages.push({ role: m.role, content: m.content })
      }
    }

    const res = await api.proxyChat(
      payloadMessages,
      selectedProvider.value === 'openrouter' ? (openRouterKey.value?.provider || 'openrouter') : selectedProvider.value,
      effectiveModel.value || null,
      null,
      temperature.value
    )

    messages.value.push({
      role: 'assistant',
      content: res.content,
      model: res.model,
      provider: res.provider,
      latency_ms: res.latency_ms,
      tokens: res.usage?.total_tokens || 0,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    })
    persistChat()
  } catch (err) {
    messages.value.push({
      role: 'error',
      content: `[Error al comunicar con upstream]: ${err.message || err}`,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    })
    persistChat()
  } finally {
    isThinking.value = false
    await scrollToBottom()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

onMounted(async () => {
  loadPreferences()
  try {
    vaultKeys.value = await api.getVaultKeys()
    if (selectedProvider.value === 'custom_llm' && openRouterKey.value?.provider === 'custom_llm') selectedProvider.value = 'openrouter'
    if (selectedProvider.value === 'openrouter' && openRouterKey.value) {
      selectedOpenRouterPreset.value = openRouterKey.value.model_name || selectedOpenRouterPreset.value
      await loadModels()
    }
  } catch {
    vaultKeys.value = []
  } finally {
    isLoadingKeys.value = false
  }
  await scrollToBottom()
})
</script>
