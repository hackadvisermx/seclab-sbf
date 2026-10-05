<template>
  <div class="space-y-8">
    <!-- Header de bienvenida táctica -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1b253b] pb-6">
      <div>
        <h1 class="text-2xl font-mono font-bold text-white flex items-center space-x-3">
          <span>🛡️ Centro de Mando Táctico</span>
          <span class="text-xs px-2 py-0.5 rounded-sm bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono">
            ESTACIÓN ACTIVA
          </span>
        </h1>
        <p class="text-slate-400 text-sm mt-1">
          Gobierno de auditorías, gestión de alcance determinista y almacén de claves Hermes para SecLab-SBF.
        </p>
      </div>

      <div class="flex items-center space-x-3">
        <router-link
          to="/engagements"
          class="px-4 py-2 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-semibold text-sm transition-all shadow-md shadow-cyan-500/20 flex items-center space-x-2"
        >
          <span>+</span>
          <span>Nueva Auditoría</span>
        </router-link>
        <router-link
          to="/vault"
          class="px-4 py-2 rounded-sm bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-mono text-sm transition-all flex items-center space-x-2"
        >
          <span>🔑</span>
          <span>API Vault</span>
        </router-link>
      </div>
    </div>

    <!-- Tarjetas Métricas Clave -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      <div class="tactical-card">
        <div class="flex items-center justify-between">
          <span class="text-xs font-mono text-slate-400 uppercase tracking-wider">Engagements</span>
          <span class="text-lg">🎯</span>
        </div>
        <div class="text-3xl font-mono font-bold text-white mt-2">{{ engSummary.engagementsCount }}</div>
        <div class="text-xs text-slate-400 mt-1 flex items-center space-x-1">
          <span class="text-cyan-400">Bug Bounty & Pentests</span>
        </div>
      </div>

      <div class="tactical-card">
        <div class="flex items-center justify-between">
          <span class="text-xs font-mono text-slate-400 uppercase tracking-wider">Retos & CTFs</span>
          <span class="text-lg">🚩</span>
        </div>
        <div class="text-3xl font-mono font-bold text-white mt-2">{{ engSummary.retosCount }}</div>
        <div class="text-xs text-slate-400 mt-1 flex items-center space-x-1">
          <span class="text-emerald-400">Máquinas & Plataformas</span>
        </div>
      </div>

      <div class="tactical-card">
        <div class="flex items-center justify-between">
          <span class="text-xs font-mono text-slate-400 uppercase tracking-wider">Fichas de Evidencia</span>
          <span class="text-lg">📋</span>
        </div>
        <div class="text-3xl font-mono font-bold text-white mt-2">{{ engSummary.totalEvidence }}</div>
        <div class="text-xs text-slate-400 mt-1 flex items-center space-x-1">
          <span class="text-amber-400">Principio Evidence-First</span>
        </div>
      </div>

      <div class="tactical-card">
        <div class="flex items-center justify-between">
          <span class="text-xs font-mono text-slate-400 uppercase tracking-wider">SecLab API Keys</span>
          <span class="text-lg">⚡</span>
        </div>
        <div class="text-3xl font-mono font-bold text-white mt-2">{{ vaultCount }}</div>
        <div class="text-xs text-slate-400 mt-1 flex items-center space-x-1">
          <span class="text-cyan-400">{{ onlineVaultCount }} llaves verificadas</span>
        </div>
      </div>
    </div>

    <!-- Verificador Rápido de Alcance (Scope Guard) -->
    <div class="tactical-card bg-linear-to-r from-[#0d1322] to-[#0f172a]">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
        <div>
          <h2 class="text-base font-mono font-bold text-white flex items-center space-x-2">
            <span>🛡️ Validador Instantáneo de Alcance (Scope Guard)</span>
          </h2>
          <p class="text-xs text-slate-400">
            Comprueba en tiempo real si un host, IP o URL está explícitamente autorizado o bloqueado por target.yaml.
          </p>
        </div>

        <div v-if="engagements.length > 0" class="flex items-center space-x-2">
          <span class="text-xs font-mono text-slate-400">Contexto:</span>
          <select
            v-model="selectedEngId"
            class="bg-slate-900 border border-slate-700 rounded-sm px-2.5 py-1 text-xs font-mono text-cyan-300 focus:outline-hidden focus:border-cyan-500"
          >
            <option v-for="e in engagements" :key="e.id" :value="e.id">
              {{ e.name }} ({{ e.type }})
            </option>
          </select>
        </div>
      </div>

      <form @submit.prevent="runScopeCheck" class="flex flex-col sm:flex-row items-center gap-3">
        <div class="relative flex-1 w-full">
          <input
            v-model="targetInput"
            type="text"
            placeholder="Ejemplo: target.local, 192.168.1.10, api.subdominio.com"
            class="w-full bg-[#070b14] border border-[#1b253b] focus:border-cyan-400 rounded-sm px-4 py-2 text-sm font-mono text-slate-100 placeholder-slate-500 focus:outline-hidden focus:ring-1 focus:ring-cyan-400"
          />
        </div>
        <button
          type="submit"
          :disabled="isCheckingScope || !targetInput.trim()"
          class="w-full sm:w-auto px-5 py-2 rounded-sm bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-mono font-semibold text-sm transition-all shadow-md shadow-cyan-600/20 whitespace-nowrap"
        >
          {{ isCheckingScope ? 'Verificando...' : 'Verificar Alcance' }}
        </button>
      </form>

      <!-- Resultado de Scope Check -->
      <div v-if="scopeResult" class="mt-4 p-3 rounded-sm border text-xs font-mono" :class="scopeResultClass">
        <div class="flex items-center space-x-2 font-bold text-sm">
          <span>{{ scopeResult.allowed ? '✅ OBJETIVO AUTORIZADO' : '🚫 ACCIÓN BLOQUEADA' }}</span>
          <span class="text-xs opacity-75">({{ scopeResult.status }})</span>
        </div>
        <p class="mt-1">{{ scopeResult.reason }}</p>
      </div>
    </div>

    <!-- Lista de Auditorías Activas & Telemetría -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Tabla de Engagements Recientes -->
      <div class="lg:col-span-2 tactical-card space-y-4">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider flex items-center space-x-2">
            <span>📁 Auditorías y Retos en Workspace</span>
          </h2>
          <router-link to="/engagements" class="text-xs font-mono text-cyan-400 hover:underline">
            Ver todos ({{ engagements.length }}) &rarr;
          </router-link>
        </div>

        <div v-if="isLoading" class="text-center py-8 text-slate-400 font-mono text-xs">
          Cargando registros desde /workspace...
        </div>

        <div v-else-if="engagements.length === 0" class="text-center py-8 text-slate-400 font-mono text-xs space-y-2">
          <p>No se encontraron auditorías ni retos activos en /workspace.</p>
          <router-link to="/engagements" class="inline-block px-3 py-1.5 rounded-sm bg-cyan-600 text-black font-semibold text-xs">
            Crear Primer Engagement
          </router-link>
        </div>

        <div v-else class="divide-y divide-slate-800/80">
          <div
            v-for="item in engagements.slice(0, 5)"
            :key="item.id"
            class="py-3 flex items-center justify-between hover:bg-slate-800/20 px-2 rounded-sm transition-colors"
          >
            <div class="flex items-center space-x-3">
              <span class="text-xl">{{ item.type === 'reto' ? '🚩' : '🎯' }}</span>
              <div>
                <router-link
                  :to="`/engagements/${item.type}/${item.id}`"
                  class="font-mono font-semibold text-sm text-cyan-300 hover:text-cyan-200 hover:underline"
                >
                  {{ item.name }}
                </router-link>
                <div class="flex items-center space-x-2 text-[11px] text-slate-400 font-mono mt-0.5">
                  <span class="px-1.5 py-0.2 rounded-sm bg-slate-800 border border-slate-700 text-slate-300">
                    {{ item.type }}
                  </span>
                  <span>{{ item.client_or_platform }}</span>
                  <span>•</span>
                  <span>{{ item.created_at }}</span>
                </div>
              </div>
            </div>

            <div class="flex items-center space-x-4 text-xs font-mono">
              <div class="text-right hidden sm:block">
                <div class="text-slate-200 font-semibold">{{ item.evidence_count }} evidencias</div>
                <div class="text-[10px] text-slate-400">{{ item.terminal_log_lines }} líneas log</div>
              </div>
              <router-link
                :to="`/engagements/${item.type}/${item.id}`"
                class="px-2.5 py-1 rounded-sm bg-slate-800 hover:bg-slate-700 text-cyan-400 border border-slate-700 text-xs"
              >
                Abrir
              </router-link>
            </div>
          </div>
        </div>
      </div>

      <!-- Telemetría de Red y Workspace -->
      <div class="tactical-card space-y-5">
        <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider border-b border-slate-800 pb-3 flex items-center space-x-2">
          <span>📡 Telemetría del Entorno</span>
        </h2>

        <!-- Espacio en Workspace -->
        <div class="space-y-2">
          <div class="flex items-center justify-between text-xs font-mono">
            <span class="text-slate-400">Espacio en /workspace:</span>
            <span class="text-cyan-300 font-bold">
              {{ telemetry.disk?.used_gb || 0 }} GB / {{ telemetry.disk?.total_gb || 0 }} GB ({{ telemetry.disk?.percent || 0 }}%)
            </span>
          </div>
          <div class="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
            <div
              class="h-full bg-cyan-500 rounded-full transition-all duration-500"
              :style="{ width: `${telemetry.disk?.percent || 0}%` }"
            ></div>
          </div>
        </div>

        <!-- Conexiones de Red -->
        <div class="space-y-2 text-xs font-mono">
          <div class="p-2.5 rounded-sm bg-slate-900/80 border border-slate-800 flex items-center justify-between">
            <span class="text-slate-400">VPN Activa (tun0):</span>
            <span
              class="px-2 py-0.5 rounded-sm text-[11px] font-bold"
              :class="telemetry.vpn?.connected ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'"
            >
              {{ telemetry.vpn?.connected ? telemetry.vpn.ip : 'DESCONECTADO' }}
            </span>
          </div>

          <div class="p-2.5 rounded-sm bg-slate-900/80 border border-slate-800 flex items-center justify-between">
            <span class="text-slate-400">Tailscale Nodo:</span>
            <span
              class="px-2 py-0.5 rounded-sm text-[11px] font-bold"
              :class="telemetry.tailscale?.online ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'bg-slate-800 text-slate-400'"
            >
              {{ telemetry.tailscale?.online ? telemetry.tailscale.ip : 'HOST-ONLY' }}
            </span>
          </div>

          <div class="p-2.5 rounded-sm bg-slate-900/80 border border-slate-800 flex items-center justify-between">
            <span class="text-slate-400">Sesiones tmux:</span>
            <span class="text-slate-200">
              {{ telemetry.tmux_sessions?.length > 0 ? telemetry.tmux_sessions.join(', ') : 'Ninguna activa' }}
            </span>
          </div>
        </div>

        <!-- Atajos Rápidos -->
        <div class="pt-2 border-t border-slate-800 space-y-2">
          <span class="text-[11px] font-mono text-slate-400 uppercase">Comandos Tácticos en Terminal:</span>
          <div class="grid grid-cols-2 gap-2 text-xs font-mono">
            <div class="p-1.5 rounded-sm bg-slate-900 border border-slate-800 text-slate-300">
              <code>pt-help</code>
            </div>
            <div class="p-1.5 rounded-sm bg-slate-900 border border-slate-800 text-slate-300">
              <code>pt-cheat</code>
            </div>
            <div class="p-1.5 rounded-sm bg-slate-900 border border-slate-800 text-slate-300">
              <code>pt-scope show</code>
            </div>
            <div class="p-1.5 rounded-sm bg-slate-900 border border-slate-800 text-slate-300">
              <code>pt-report build</code>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'

const engagements = ref([])
const vaultKeys = ref([])
const telemetry = ref({})
const isLoading = ref(true)

const selectedEngId = ref('')
const targetInput = ref('')
const isCheckingScope = ref(false)
const scopeResult = ref(null)

const engSummary = computed(() => {
  const engs = engagements.value.filter(e => e.type === 'engagement')
  const retos = engagements.value.filter(e => e.type === 'reto')
  const totalEv = engagements.value.reduce((acc, curr) => acc + (curr.evidence_count || 0), 0)
  return {
    engagementsCount: engs.length,
    retosCount: retos.length,
    totalEvidence: totalEv,
  }
})

const vaultCount = computed(() => vaultKeys.value.length)
const onlineVaultCount = computed(() => vaultKeys.value.filter(k => k.status === 'online').length)

const scopeResultClass = computed(() => {
  if (!scopeResult.value) return ''
  return scopeResult.value.allowed
    ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
    : 'bg-red-950/40 border-red-500/40 text-red-300'
})

async function runScopeCheck() {
  if (!targetInput.value.trim() || !selectedEngId.value) return
  isCheckingScope.value = true
  scopeResult.value = null
  try {
    const selected = engagements.value.find(e => e.id === selectedEngId.value)
    const res = await api.checkScope(targetInput.value.trim(), selectedEngId.value, selected?.type || 'engagement')
    scopeResult.value = res
  } catch (err) {
    scopeResult.value = {
      allowed: false,
      status: 'ERROR',
      reason: err.message,
    }
  } finally {
    isCheckingScope.value = false
  }
}

async function loadData() {
  isLoading.value = true
  try {
    const [engs, keys, telem] = await Promise.all([
      api.getEngagements(),
      api.getVaultKeys(),
      api.getTelemetry(),
    ])
    engagements.value = engs
    vaultKeys.value = keys
    telemetry.value = telem
    if (engs.length > 0 && !selectedEngId.value) {
      selectedEngId.value = engs[0].id
    }
  } catch (err) {
    console.error('Error al cargar datos del dashboard:', err)
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>
