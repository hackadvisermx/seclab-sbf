<template>
  <header class="bg-[#0b101d] border-b border-[#1b253b] sticky top-0 z-50 px-6 py-3">
    <div class="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
      <!-- Logo y Brand -->
      <div class="flex items-center space-x-6">
        <router-link to="/" class="flex items-center space-x-3 group">
          <div class="w-9 h-9 rounded-sm bg-[#131d31] border border-cyan-500/40 flex items-center justify-center text-cyan-400 font-mono font-bold shadow-lg shadow-cyan-500/10 group-hover:border-cyan-400 transition-colors">
            ⚡
          </div>
          <div>
            <span class="font-mono font-bold text-lg tracking-wider text-slate-100 flex items-center space-x-2">
              <span>SECLAB</span>
              <span class="text-xs px-1.5 py-0.5 rounded-sm bg-cyan-950/80 border border-cyan-500/30 text-cyan-400">TACTICAL</span>
            </span>
            <p class="text-[10px] font-mono text-slate-400">AUDIT SUITE & KEY VAULT</p>
          </div>
        </router-link>

        <!-- Navegación Principal -->
        <nav class="hidden md:flex items-center space-x-1 pl-4 border-l border-slate-800">
          <router-link
            to="/"
            class="px-3 py-1.5 rounded-sm text-sm font-medium transition-all"
            :class="$route.path === '/' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'"
          >
            Dashboard
          </router-link>
          <router-link
            to="/engagements"
            class="px-3 py-1.5 rounded-sm text-sm font-medium transition-all"
            :class="$route.path.startsWith('/engagements') ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'"
          >
            Auditorías & Retos
          </router-link>
          <router-link
            to="/terminal"
            class="px-3 py-1.5 rounded-sm text-sm font-medium transition-all flex items-center space-x-1.5"
            :class="$route.path === '/terminal' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'"
          >
            <span>💻</span>
            <span>Terminal</span>
          </router-link>
          <router-link
            to="/vault"
            class="px-3 py-1.5 rounded-sm text-sm font-medium transition-all flex items-center space-x-1.5"
            :class="$route.path === '/vault' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'"
          >
            <span>API Vault</span>
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          </router-link>
          <router-link
            to="/help"
            class="px-3 py-1.5 rounded-sm text-sm font-medium transition-all"
            :class="$route.path === '/help' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30' : 'text-slate-300 hover:text-white hover:bg-slate-800/60'"
          >
            Ayuda & Acceso
          </router-link>
        </nav>
      </div>

      <!-- Telemetría & Accesos Rápidos -->
      <div class="flex items-center space-x-3 text-xs font-mono relative">
        <!-- VPN Status Widget & Dropdown Trigger -->
        <div class="relative">
          <button
            @click="vpnDropdownOpen = !vpnDropdownOpen"
            class="flex items-center space-x-1.5 px-2.5 py-1 rounded-sm bg-[#0d1322] border transition-all cursor-pointer focus:outline-hidden"
            :class="vpnBadgeClasses"
            title="Haz clic para gestionar la conexión VPN táctica"
          >
            <span class="w-2 h-2 rounded-full" :class="vpnIndicatorClasses"></span>
            <span>{{ vpnBadgeText }}</span>
            <span class="text-[10px] text-slate-500 ml-0.5">▼</span>
          </button>

          <!-- Dropdown Táctico VPN -->
          <div
            v-if="vpnDropdownOpen"
            class="absolute left-0 sm:left-auto sm:right-0 mt-2 w-84 max-w-[calc(100vw-3rem)] rounded-lg bg-[#0e1628] border border-cyan-500/40 shadow-2xl p-4 z-50 text-slate-200 font-mono space-y-3"
          >
            <!-- Header con Switch Estado -->
            <div class="flex items-center justify-between border-b border-slate-800 pb-2">
              <span class="font-bold text-xs uppercase tracking-wider text-cyan-400 flex items-center space-x-1.5">
                <span>🛡️</span>
                <span>Control Táctico VPN</span>
              </span>
              <div class="flex items-center space-x-2">
                <span
                  class="px-1.5 py-0.5 rounded-sm text-[10px] uppercase font-bold"
                  :class="telemetry.vpn?.connected ? 'bg-emerald-950 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'"
                >
                  {{ telemetry.vpn?.connecting ? 'CONECTANDO' : (telemetry.vpn?.connected ? 'ENCENDIDO' : 'APAGADO') }}
                </span>
                <button
                  @click="vpnActive ? handleDisconnectVpn() : handleConnectWithSelected()"
                  :disabled="vpnLoading"
                  class="px-2 py-0.5 rounded-sm border text-[10px] font-bold cursor-pointer disabled:opacity-50"
                  :class="vpnActive ? 'bg-rose-950/80 hover:bg-rose-900 border-rose-500/50 text-rose-300' : 'bg-emerald-950/80 hover:bg-emerald-900 border-emerald-500/50 text-emerald-300'"
                  :title="vpnActive ? 'Apagar túnel VPN' : 'Encender el perfil seleccionado'"
                >
                  {{ vpnLoading ? 'PROCESANDO…' : (vpnActive ? 'APAGAR' : 'ENCENDER') }}
                </button>
              </div>
            </div>

            <!-- Detalles de Red -->
            <div class="space-y-1 text-[11px] bg-slate-900/80 p-2.5 rounded-sm border border-slate-800">
              <div class="flex justify-between">
                <span class="text-slate-400">Perfil Activo:</span>
                <span class="font-bold text-cyan-300 capitalize">{{ telemetry.vpn?.profile || 'Ninguno' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-slate-400">Interfaz:</span>
                <span>{{ telemetry.vpn?.interface || 'tun0' }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-slate-400">IP Asignada:</span>
                <span class="text-emerald-400 font-bold">{{ telemetry.vpn?.ip || 'Sin asignar' }}</span>
              </div>
            </div>

            <!-- Selector de Perfil -->
            <div class="space-y-1">
              <label class="text-[10px] text-slate-400 uppercase font-semibold">Seleccionar Perfil:</label>
              <div class="grid grid-cols-3 gap-1.5">
                <button
                  type="button"
                  @click="selectedProfile = 'tryhackme'"
                  class="px-2 py-1.5 rounded-sm text-[10px] font-bold border transition-all text-center cursor-pointer"
                  :class="selectedProfile === 'tryhackme' ? 'bg-emerald-950 border-emerald-400 text-emerald-300 shadow-xs' : 'bg-slate-900/70 border-slate-800 text-slate-400 hover:text-slate-200'"
                >
                  TryHackMe
                </button>
                <button
                  type="button"
                  @click="selectedProfile = 'hackthebox'"
                  class="px-2 py-1.5 rounded-sm text-[10px] font-bold border transition-all text-center cursor-pointer"
                  :class="selectedProfile === 'hackthebox' ? 'bg-amber-950 border-amber-400 text-amber-300 shadow-xs' : 'bg-slate-900/70 border-slate-800 text-slate-400 hover:text-slate-200'"
                >
                  HackTheBox
                </button>
                <button
                  type="button"
                  @click="selectedProfile = 'client'"
                  class="px-2 py-1.5 rounded-sm text-[10px] font-bold border transition-all text-center cursor-pointer"
                  :class="selectedProfile === 'client' ? 'bg-blue-950 border-blue-400 text-blue-300 shadow-xs' : 'bg-slate-900/70 border-slate-800 text-slate-400 hover:text-slate-200'"
                >
                  Cliente
                </button>
              </div>
            </div>

            <!-- Opciones de Autenticación -->
            <div class="space-y-2 pt-1 border-t border-slate-800/80">
              <div class="flex items-center justify-between">
                <label class="text-[10px] text-slate-400 uppercase font-semibold">Credenciales (Opcional):</label>
                <button
                  type="button"
                  @click="showAuthInputs = !showAuthInputs"
                  class="text-[10px] text-cyan-400 hover:underline cursor-pointer"
                >
                  {{ showAuthInputs ? 'Ocultar' : (hasSavedCredentials ? '🔒 Guardadas en Vault' : '+ Añadir') }}
                </button>
              </div>

              <!-- Formulario de Credenciales Expandible -->
              <div v-if="showAuthInputs" class="space-y-2 bg-[#070b14] p-2.5 rounded-sm border border-slate-800 text-xs">
                <div>
                  <label class="text-[10px] text-slate-400 block mb-0.5">Usuario:</label>
                  <input
                    v-model="vpnUsername"
                    type="text"
                    placeholder="ej. vpn_user"
                    class="w-full bg-slate-900 border border-slate-700 rounded-sm px-2 py-1 text-slate-200 text-xs font-mono focus:border-cyan-400 focus:outline-hidden"
                  />
                </div>
                <div>
                  <label class="text-[10px] text-slate-400 block mb-0.5">Contraseña:</label>
                  <input
                    v-model="vpnPassword"
                    type="password"
                    placeholder="••••••••"
                    class="w-full bg-slate-900 border border-slate-700 rounded-sm px-2 py-1 text-slate-200 text-xs font-mono focus:border-cyan-400 focus:outline-hidden"
                  />
                </div>
                <div class="flex items-center justify-between pt-1">
                  <label class="flex items-center space-x-1.5 text-[10px] text-slate-300 cursor-pointer">
                    <input
                      v-model="vpnSaveInVault"
                      type="checkbox"
                      class="rounded-sm bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
                    />
                    <span>Guardar en Vault (AES-256)</span>
                  </label>
                  <button
                    v-if="hasSavedCredentials"
                    type="button"
                    @click="handleDeleteSavedCredentials"
                    class="text-[10px] text-rose-400 hover:underline cursor-pointer"
                  >
                    Olvidar
                  </button>
                </div>
              </div>
            </div>

            <!-- Mensaje de Feedback -->
            <div v-if="vpnMessage" class="p-2 rounded-sm text-[11px] border" :class="vpnMsgSuccess ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300' : 'bg-rose-950/60 border-rose-500/40 text-rose-300'">
              {{ vpnMessage }}
            </div>

            <!-- Botones de Acción de Conexión -->
            <div class="space-y-1.5 pt-1">
              <button
                @click="handleConnectWithSelected"
                :disabled="vpnLoading || (vpnActive && telemetry.vpn?.profile === selectedProfile)"
                class="w-full py-2 px-3 rounded-sm font-mono font-bold text-xs transition-all flex items-center justify-center space-x-1.5 shadow-md cursor-pointer disabled:opacity-50"
                :class="telemetry.vpn?.connected ? 'bg-cyan-600 hover:bg-cyan-500 text-slate-950' : 'bg-emerald-600 hover:bg-emerald-500 text-slate-950'"
              >
                <span>{{ vpnLoading ? '⏳' : '⚡' }}</span>
                <span>{{ vpnLoading ? 'Procesando...' : (vpnActive && telemetry.vpn?.profile === selectedProfile ? 'Perfil activo' : (vpnActive ? `Conmutar a ${selectedProfile}` : `Encender VPN (${selectedProfile})`)) }}</span>
              </button>

              <button
                v-if="vpnActive"
                @click="handleDisconnectVpn"
                :disabled="vpnLoading"
                class="w-full py-1.5 px-3 rounded-sm bg-rose-950/70 hover:bg-rose-900 border border-rose-600/50 text-rose-300 text-xs font-bold transition-all flex items-center justify-center space-x-1.5 disabled:opacity-50 cursor-pointer"
              >
                <span>⏹</span>
                <span>Apagar VPN</span>
              </button>
            </div>

            <!-- Footer rápido -->
            <div class="text-[10px] text-slate-500 text-center pt-1 border-t border-slate-800">
              CLI: <code class="text-cyan-400">vpntry</code> | <code class="text-amber-400">vpnhtb</code> | <code class="text-blue-400">vpncli</code>
            </div>
          </div>
        </div>

        <!-- Tailscale Status -->
        <div
          class="hidden lg:flex items-center space-x-1.5 px-2.5 py-1 rounded-sm bg-[#0d1322] border"
          :class="telemetry.tailscale?.online ? 'border-cyan-500/40 text-cyan-400' : 'border-slate-800 text-slate-400'"
          title="Malla privada Tailscale"
        >
          <span class="w-2 h-2 rounded-full" :class="telemetry.tailscale?.online ? 'bg-cyan-400' : 'bg-slate-600'"></span>
          <span>TS: {{ telemetry.tailscale?.ip || (telemetry.tailscale?.installed ? 'ready' : 'host-only') }}</span>
        </div>

        <!-- Botón Terminal Web -->
        <a
          href="http://localhost:7681"
          target="_blank"
          class="flex items-center space-x-1 px-3 py-1 rounded-sm bg-slate-800 hover:bg-cyan-950/80 border border-slate-700 hover:border-cyan-500/40 text-slate-200 hover:text-cyan-300 transition-colors shadow-xs"
          title="Abrir terminal autenticada en el puerto 7681 (ttyd)"
        >
          <span>>_</span>
          <span>Terminal Web</span>
        </a>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api'

const telemetry = ref({
  vpn: { connected: false, ip: null, profile: 'none', interface: 'tun0' },
  tailscale: { online: false, ip: null, installed: false },
})

const vpnDropdownOpen = ref(false)
const vpnLoading = ref(false)
const vpnMessage = ref('')
const vpnMsgSuccess = ref(true)

const selectedProfile = ref('tryhackme')
const showAuthInputs = ref(false)
const vpnUsername = ref('')
const vpnPassword = ref('')
const vpnSaveInVault = ref(false)
const savedProfiles = ref({})
const vpnActive = computed(() => !!(telemetry.value.vpn?.connected || telemetry.value.vpn?.connecting))

const hasSavedCredentials = computed(() => {
  return !!savedProfiles.value[selectedProfile.value]?.has_credentials
})

let timer = null

const vpnBadgeClasses = computed(() => {
  const v = telemetry.value.vpn
  if (!v || !v.connected) {
    return 'border-slate-800 text-slate-400 hover:border-slate-700'
  }
  const prof = (v.profile || '').toLowerCase()
  if (prof.includes('try') || prof.includes('thm')) {
    return 'border-emerald-500/50 bg-emerald-950/30 text-emerald-300 hover:border-emerald-400'
  }
  if (prof.includes('htb') || prof.includes('hack')) {
    return 'border-amber-500/50 bg-amber-950/30 text-amber-300 hover:border-amber-400'
  }
  if (prof.includes('client') || prof.includes('cli')) {
    return 'border-blue-500/50 bg-blue-950/30 text-blue-300 hover:border-blue-400'
  }
  return 'border-emerald-500/40 text-emerald-400 hover:border-emerald-300'
})

const vpnIndicatorClasses = computed(() => {
  const v = telemetry.value.vpn
  if (!v || !v.connected) return 'bg-slate-600'
  const prof = (v.profile || '').toLowerCase()
  if (prof.includes('try') || prof.includes('thm')) return 'bg-emerald-400 animate-pulse'
  if (prof.includes('htb') || prof.includes('hack')) return 'bg-amber-400 animate-pulse'
  if (prof.includes('client') || prof.includes('cli')) return 'bg-blue-400 animate-pulse'
  return 'bg-emerald-400 animate-pulse'
})

const vpnBadgeText = computed(() => {
  const v = telemetry.value.vpn
  if (v?.connecting) return 'VPN: conectando…'
  if (!v || !v.connected) return 'VPN: offline'
  const prof = (v.profile || '').toLowerCase()
  const shortProf = prof.includes('try') ? 'THM' : (prof.includes('htb') || prof.includes('hack')) ? 'HTB' : prof.includes('client') ? 'CLI' : 'VPN'
  return `${shortProf}: ${v.ip || 'tun0'}`
})

async function loadTelemetry() {
  try {
    const data = await api.getTelemetry()
    telemetry.value = data
  } catch (err) {
    console.error('Error al cargar telemetría:', err)
  }
}

async function loadSavedCredentials() {
  try {
    const res = await api.getSavedVpnCredentials()
    savedProfiles.value = res || {}
    if (hasSavedCredentials.value && !vpnUsername.value) {
      vpnUsername.value = savedProfiles.value[selectedProfile.value]?.username || ''
    }
  } catch (err) {
    console.error('Error al listar credenciales VPN:', err)
  }
}

async function handleConnectWithSelected() {
  if (vpnLoading.value) return
  vpnLoading.value = true
  vpnMessage.value = ''
  try {
    const payload = {
      profile: selectedProfile.value,
      username: vpnUsername.value.trim() || null,
      password: vpnPassword.value || null,
      save_in_vault: vpnSaveInVault.value,
    }
    const res = vpnActive.value
      ? await api.switchVpn(payload)
      : await api.connectVpn(payload)

    vpnMsgSuccess.value = res.success
    vpnMessage.value = res.message || 'Comando enviado a vpn-control'
    if (res.success && !vpnSaveInVault.value) {
      vpnPassword.value = ''
    }
    await loadTelemetry()
    await loadSavedCredentials()
  } catch (err) {
    vpnMsgSuccess.value = false
    vpnMessage.value = err.message || 'Error al conectar VPN'
  } finally {
    vpnLoading.value = false
  }
}

async function handleDeleteSavedCredentials() {
  try {
    await api.deleteSavedVpnCredentials(selectedProfile.value)
    vpnUsername.value = ''
    vpnPassword.value = ''
    await loadSavedCredentials()
  } catch (err) {
    console.error('Error al borrar credenciales:', err)
  }
}

async function handleDisconnectVpn() {
  if (vpnLoading.value) return
  vpnLoading.value = true
  vpnMessage.value = ''
  try {
    const res = await api.disconnectVpn()
    vpnMsgSuccess.value = res.success
    vpnMessage.value = res.message || 'VPN apagada'
    await loadTelemetry()
  } catch (err) {
    vpnMsgSuccess.value = false
    vpnMessage.value = err.message || 'Error al desconectar VPN'
  } finally {
    vpnLoading.value = false
  }
}

onMounted(() => {
  loadTelemetry()
  loadSavedCredentials()
  timer = setInterval(() => {
    if (!vpnLoading.value) loadTelemetry()
  }, 2000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
