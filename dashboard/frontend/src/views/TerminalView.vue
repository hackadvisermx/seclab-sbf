<template>
  <div class="space-y-4">
    <!-- Header de la Terminal -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#0d1322] border border-[#1b253b] p-4 rounded-lg">
      <div>
        <div class="flex items-center space-x-2 text-xs font-mono mb-1" :class="isConnected ? 'text-cyan-400' : 'text-slate-400'">
          <span class="w-2 h-2 rounded-full" :class="isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'"></span>
          <span>{{ isConnected ? 'ESTACIÓN DE TRABAJO EN VIVO (TTYD)' : 'TERMINAL INTEGRADA PAUSADA' }}</span>
          <span class="text-slate-500">•</span>
          <span class="text-slate-400">Usuario: tester</span>
          <span class="text-slate-500">•</span>
          <span class="text-slate-400">Puerto :7681</span>
        </div>
        <h1 class="text-xl font-mono font-bold text-white flex items-center space-x-2">
          <span>💻 Terminal Táctico Web</span>
        </h1>
      </div>

      <!-- Acciones de Cabecera -->
      <div class="flex flex-wrap items-center gap-2 text-xs font-mono">
        <button
          @click="showSshModal = true"
          class="px-3 py-1.5 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all flex items-center space-x-1.5 cursor-pointer"
        >
          <span>🔑</span>
          <span>Acceso SSH (:2222)</span>
        </button>

        <button
          v-if="isConnected"
          @click="disconnectTerminal('Terminal integrada pausada manualmente por el operador.')"
          class="px-3 py-1.5 rounded-sm bg-slate-800 hover:bg-rose-950/60 text-slate-300 hover:text-rose-300 border border-slate-700 hover:border-rose-500/40 transition-all flex items-center space-x-1.5 cursor-pointer"
          title="Desconectar frame integrado para liberar la sesión"
        >
          <span>⏹</span>
          <span>Desconectar</span>
        </button>

        <button
          v-else
          @click="connectTerminal"
          class="px-3 py-1.5 rounded-sm bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-500/50 text-emerald-300 transition-all flex items-center space-x-1.5 cursor-pointer font-bold shadow-xs"
          title="Conectar terminal integrada"
        >
          <span>▶</span>
          <span>Conectar Integrada</span>
        </button>

        <button
          v-if="isConnected"
          @click="reloadIframe"
          class="px-3 py-1.5 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all flex items-center space-x-1.5 cursor-pointer"
          title="Recargar frame de terminal"
        >
          <span>🔄</span>
          <span>Recargar</span>
        </button>

        <button
          @click="openInNewTab"
          class="px-3 py-1.5 rounded-sm bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold transition-all flex items-center space-x-1.5 cursor-pointer shadow-xs"
          title="Abrir en pestaña externa y liberar terminal integrada"
        >
          <span>↗</span>
          <span>Nueva Pestaña</span>
        </button>
      </div>
    </div>

    <!-- Barra Táctica de Comandos Rápidos -->
    <div class="bg-[#090d18] border border-slate-800 rounded-lg p-3 flex flex-wrap items-center gap-2 text-xs font-mono">
      <span class="text-slate-400 font-bold text-[11px] uppercase mr-1">Atajos Tácticos:</span>

      <button
        v-for="c in quickCommands"
        :key="c.cmd"
        @click="copyCommand(c.cmd)"
        class="px-2.5 py-1 rounded-sm bg-slate-900 border border-slate-800 hover:border-cyan-500/50 text-slate-300 hover:text-cyan-300 transition-all flex items-center space-x-1.5 group cursor-pointer"
        :title="c.desc"
      >
        <span class="text-cyan-400 group-hover:scale-110 transition-transform">{{ c.icon }}</span>
        <span class="font-bold">{{ c.cmd }}</span>
      </button>

      <span v-if="copiedText" class="text-emerald-400 text-[11px] font-bold ml-2 animate-bounce">
        ✓ Copiado: "{{ copiedText }}"
      </span>
    </div>

    <!-- Banner de Autenticación y Estado ttyd -->
    <div class="bg-cyan-950/30 border border-cyan-800/40 rounded-lg p-3 text-xs font-mono text-slate-300 flex flex-col md:flex-row md:items-center justify-between gap-2">
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-cyan-400 font-bold">🔐 Credenciales Web:</span>
        <span>Usuario: <code class="text-emerald-400 bg-slate-900 px-1 py-0.5 rounded-sm">tester</code></span>
        <span class="text-slate-500">•</span>
        <span>Contraseña: la configurada para el laboratorio</span>
      </div>
      <div class="text-[11px] text-slate-400">
        Si el navegador restringe autenticación en marcos, pulse
        <button @click="openInNewTab" class="text-cyan-400 underline hover:text-cyan-300 font-bold cursor-pointer">↗ Nueva Pestaña</button> para iniciar sesión.
      </div>
    </div>

    <!-- Contenedor del Iframe ttyd -->
    <div class="tactical-card p-1 bg-[#050811] border-cyan-500/30 overflow-hidden relative rounded-lg">
      <iframe
        v-if="isConnected"
        ref="terminalFrame"
        :src="terminalUrl"
        class="w-full h-[720px] rounded-sm border-0 bg-black"
        allow="clipboard-read; clipboard-write"
      ></iframe>
      <div
        v-else
        class="w-full min-h-[420px] flex flex-col items-center justify-center p-8 text-center space-y-4 font-mono bg-[#070b14]"
      >
        <div class="w-14 h-14 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-2xl shadow-inner">
          💻
        </div>
        <div class="space-y-1.5 max-w-lg">
          <h3 class="text-base font-bold text-white flex items-center justify-center space-x-2">
            <span>Terminal Integrada Desconectada</span>
          </h3>
          <p class="text-xs text-slate-400 leading-relaxed">
            {{ detachedReason || 'La terminal integrada se encuentra en pausa o activa en una pestaña independiente.' }}
          </p>
        </div>
        <div class="flex flex-wrap items-center justify-center gap-3 pt-2">
          <button
            @click="connectTerminal"
            class="px-4 py-2 rounded-sm bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold text-xs flex items-center space-x-1.5 transition-all shadow-md cursor-pointer"
          >
            <span>🔄</span>
            <span>Reconectar Terminal Integrada</span>
          </button>
          <a
            :href="terminalUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="px-4 py-2 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs flex items-center space-x-1.5 transition-all"
          >
            <span>↗</span>
            <span>Ir a Pestaña Externa (:7681)</span>
          </a>
        </div>
      </div>
    </div>

    <!-- Modal de Credenciales y Conexión SSH -->
    <div
      v-if="showSshModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 overflow-y-auto"
    >
      <div class="bg-[#0d1322] border border-cyan-500/40 rounded-lg max-w-xl w-full p-6 shadow-2xl space-y-5">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 class="text-base font-mono font-bold text-white flex items-center space-x-2">
            <span>🔑 Parámetros de Conexión Segura</span>
          </h2>
          <button @click="showSshModal = false" class="text-slate-400 hover:text-white font-mono text-lg cursor-pointer">&times;</button>
        </div>

        <div class="space-y-4 text-xs font-mono">
          <div class="space-y-1">
            <span class="text-slate-400 font-bold block">1. SSH al Contenedor del Laboratorio (tester):</span>
            <div class="p-2.5 bg-[#050811] rounded-sm border border-slate-800 flex items-center justify-between">
              <code class="text-cyan-300">ssh -p 2222 -i .secrets/ssh/id_ed25519 tester@localhost</code>
              <button @click="copyCommand('ssh -p 2222 -i .secrets/ssh/id_ed25519 tester@localhost')" class="text-slate-400 hover:text-white text-[11px] cursor-pointer">Copiar</button>
            </div>
            <p class="text-[10px] text-slate-500">O mediante make: <code>make lab-ssh</code> o <code>make lab-ssh-cloud</code></p>
          </div>

          <div class="space-y-1">
            <span class="text-slate-400 font-bold block">2. Web Terminal (ttyd) Autenticación HTTP:</span>
            <div class="p-2.5 bg-[#050811] rounded-sm border border-slate-800 space-y-1">
              <div>Usuario: <code class="text-emerald-400">tester</code></div>
              <div>Password: <span class="text-slate-400">(Configurado en su archivo <code>.secrets/runtime/lab.env</code>)</span></div>
            </div>
          </div>

          <div class="space-y-1">
            <span class="text-slate-400 font-bold block">3. Inyección en Memoria con API Vault:</span>
            <div class="p-2.5 bg-[#050811] rounded-sm border border-slate-800 flex items-center justify-between">
              <code class="text-cyan-300">pt-vault run shodan myinfo</code>
              <button @click="copyCommand('pt-vault run shodan myinfo')" class="text-slate-400 hover:text-white text-[11px] cursor-pointer">Copiar</button>
            </div>
          </div>
        </div>

        <div class="flex justify-end pt-2 border-t border-slate-800">
          <button
            @click="showSshModal = false"
            class="px-4 py-1.5 rounded-sm bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs font-mono cursor-pointer"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const isConnected = ref(true)
const detachedReason = ref('')
const terminalFrame = ref(null)
const showSshModal = ref(false)
const copiedText = ref('')

const terminalUrl = computed(() => {
  const protocol = window.location.protocol
  const hostname = window.location.hostname || 'localhost'
  return `${protocol}//${hostname}:7681`
})

const quickCommands = [
  { cmd: 'vpntry', icon: '🛡️', desc: 'Conectar VPN TryHackMe' },
  { cmd: 'vpnhtb', icon: '🛡️', desc: 'Conectar VPN HackTheBox' },
  { cmd: 'vpncli', icon: '🛡️', desc: 'Conectar VPN Cliente Corporativo' },
  { cmd: 'pt-cheat', icon: '💡', desc: 'Catálogo Interactivo con fzf' },
  { cmd: 'pt-tools', icon: '🧰', desc: 'Arsenal Completo de Pentest' },
  { cmd: 'pt-vault list', icon: '🔐', desc: 'Listar claves del Vault' },
  { cmd: 'pt-log status', icon: '📜', desc: 'Estado de bitácora terminal.log' },
]

function openInNewTab() {
  window.open(terminalUrl.value, '_blank', 'noopener,noreferrer')
  disconnectTerminal('La terminal web se abrió en una pestaña externa. Se ha desconectado la terminal integrada para otorgarte pantalla completa y máxima resolución.')
}

function disconnectTerminal(reason = 'Terminal integrada desconectada manualmente.') {
  detachedReason.value = reason
  isConnected.value = false
}

function connectTerminal() {
  detachedReason.value = ''
  isConnected.value = true
}

function reloadIframe() {
  if (isConnected.value && terminalFrame.value) {
    terminalFrame.value.src = terminalUrl.value
  } else {
    connectTerminal()
  }
}

function copyCommand(text) {
  navigator.clipboard.writeText(text)
  copiedText.value = text
  setTimeout(() => {
    copiedText.value = ''
  }, 2500)
}

function handleTabOpenEvent() {
  disconnectTerminal('La terminal web se abrió en una pestaña externa desde la barra de navegación.')
}

onMounted(() => {
  window.addEventListener('seclab-terminal-tab-opened', handleTabOpenEvent)
})

onUnmounted(() => {
  isConnected.value = false
  window.removeEventListener('seclab-terminal-tab-opened', handleTabOpenEvent)
})
</script>
