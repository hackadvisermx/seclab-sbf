<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#1b253b] pb-6">
      <div>
        <h1 class="text-2xl font-mono font-bold text-white flex items-center space-x-3">
          <span>📖 Centro de Ayuda, Tácticas & Datos de Acceso</span>
        </h1>
        <p class="text-slate-400 text-sm mt-1">
          Comandos tácticos de terminal, catálogo interactivo pt-cheat, playbooks y datos de conectividad.
        </p>
      </div>

      <div class="flex items-center space-x-2 text-xs font-mono">
        <span class="px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
          Shell: ZSH / TMUX
        </span>
        <span class="px-2.5 py-1 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-500/30">
          Usuario: tester
        </span>
      </div>
    </div>

    <!-- Pestañas de Ayuda -->
    <div class="flex items-center space-x-2 border-b border-slate-800 pb-2 text-xs font-mono">
      <button
        v-for="t in ['access', 'cheatsheet', 'skills']"
        :key="t"
        @click="activeTab = t"
        class="px-4 py-2 rounded font-semibold transition-colors uppercase tracking-wider"
        :class="activeTab === t ? 'bg-cyan-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white bg-slate-800/40'"
      >
        {{ t === 'access' ? 'Datos de Acceso & Red' : (t === 'cheatsheet' ? 'Catálogo pt-cheat (48 comandos)' : 'Playbooks de Habilidades (skills/)') }}
      </button>
    </div>

    <!-- TAB 1: DATOS DE ACCESO & RED -->
    <div v-if="activeTab === 'access'" class="space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
        <!-- Puertos y Servicios de SecLab -->
        <div class="tactical-card space-y-4">
          <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider border-b border-slate-800 pb-2 flex items-center space-x-2">
            <span>🔌 Puertos y Servicios Internos</span>
          </h2>
          <div class="space-y-3 text-xs font-mono">
            <div class="p-3 rounded bg-slate-900/80 border border-slate-800 space-y-1">
              <div class="flex items-center justify-between font-bold">
                <span class="text-cyan-400">Web Terminal (ttyd)</span>
                <span class="text-slate-300">:7681</span>
              </div>
              <p class="text-slate-400 text-[11px]">Consola web Zsh/Tmux autenticada con usuario tester.</p>
              <div class="text-[10px] text-slate-500">Acceso: http://localhost:7681 o http://[TAILSCALE_IP]:7681</div>
            </div>

            <div class="p-3 rounded bg-slate-900/80 border border-slate-800 space-y-1">
              <div class="flex items-center justify-between font-bold">
                <span class="text-cyan-400">Tactical Dashboard & Hermes</span>
                <span class="text-slate-300">:8080</span>
              </div>
              <p class="text-slate-400 text-[11px]">Esta interfaz web y API backend de gestión.</p>
              <div class="text-[10px] text-slate-500">Acceso: http://localhost:8080 o http://[TAILSCALE_IP]:8080</div>
            </div>

            <div class="p-3 rounded bg-slate-900/80 border border-slate-800 space-y-1">
              <div class="flex items-center justify-between font-bold">
                <span class="text-cyan-400">SSH Laboratorio (tester)</span>
                <span class="text-slate-300">:2222</span>
              </div>
              <p class="text-slate-400 text-[11px]">Acceso por claves SSH (sin password, rootfs read-only).</p>
              <div class="text-[10px] text-slate-500">Comando: make lab-ssh-cloud o make lab-ssh-az</div>
            </div>

            <div class="p-3 rounded bg-slate-900/80 border border-slate-800 space-y-1">
              <div class="flex items-center justify-between font-bold">
                <span class="text-cyan-400">SSH Host (ubuntu)</span>
                <span class="text-slate-300">:22</span>
              </div>
              <p class="text-slate-400 text-[11px]">Administración del nodo VM cloud o servidor físico.</p>
              <div class="text-[10px] text-slate-500">Comando: make host-ssh-cloud o make host-ssh-az</div>
            </div>
          </div>
        </div>

        <!-- Comandos de Gestión VPN Inside -->
        <div class="tactical-card space-y-4">
          <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider border-b border-slate-800 pb-2 flex items-center space-x-2">
            <span>🛡️ Perfiles VPN (Inside Mode)</span>
          </h2>
          <p class="text-xs text-slate-400 font-mono">
            El contenedor no altera la ruta default del host. En la terminal de tester, solicita el túnel con un comando:
          </p>

          <div class="space-y-2 text-xs font-mono">
            <div class="p-2.5 rounded bg-slate-950 border border-slate-800 flex items-center justify-between">
              <div>
                <span class="text-emerald-400 font-bold block">vpntry</span>
                <span class="text-[11px] text-slate-400">Conecta TryHackMe (tryhackme.ovpn)</span>
              </div>
              <button @click="copyText('vpntry')" class="px-2 py-1 rounded bg-slate-800 text-cyan-400 text-[10px]">Copiar</button>
            </div>

            <div class="p-2.5 rounded bg-slate-950 border border-slate-800 flex items-center justify-between">
              <div>
                <span class="text-emerald-400 font-bold block">vpnhtb</span>
                <span class="text-[11px] text-slate-400">Conecta HackTheBox (hackthebox.ovpn)</span>
              </div>
              <button @click="copyText('vpnhtb')" class="px-2 py-1 rounded bg-slate-800 text-cyan-400 text-[10px]">Copiar</button>
            </div>

            <div class="p-2.5 rounded bg-slate-950 border border-slate-800 flex items-center justify-between">
              <div>
                <span class="text-emerald-400 font-bold block">vpncli</span>
                <span class="text-[11px] text-slate-400">Conecta VPN de Cliente (client.ovpn)</span>
              </div>
              <button @click="copyText('vpncli')" class="px-2 py-1 rounded bg-slate-800 text-cyan-400 text-[10px]">Copiar</button>
            </div>

            <div class="p-2.5 rounded bg-slate-950 border border-slate-800 flex items-center justify-between">
              <div>
                <span class="text-red-400 font-bold block">vpn-down</span>
                <span class="text-[11px] text-slate-400">Desconecta el túnel y limpia las rutas de tun0</span>
              </div>
              <button @click="copyText('vpn-down')" class="px-2 py-1 rounded bg-slate-800 text-cyan-400 text-[10px]">Copiar</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2: CATÁLOGO PT-CHEAT -->
    <div v-if="activeTab === 'cheatsheet'" class="space-y-4">
      <div class="flex flex-col sm:flex-row items-center justify-between gap-3">
        <input
          v-model="cheatQuery"
          type="text"
          placeholder="Buscar comandos (ej: pivoting, kerberoast, ligolo, hashcat)..."
          class="w-full sm:w-96 bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded px-3 py-1.5 text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-none"
        />
        <span class="text-xs font-mono text-slate-400">Mostrando {{ filteredCheats.length }} comandos</span>
      </div>

      <div class="tactical-card divide-y divide-slate-800/80 p-0 overflow-hidden">
        <div
          v-for="(c, idx) in filteredCheats"
          :key="idx"
          class="p-4 hover:bg-slate-800/20 transition-colors flex flex-col md:flex-row md:items-center justify-between gap-3"
        >
          <div class="space-y-1 max-w-2xl">
            <div class="flex items-center space-x-2">
              <span class="px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800 text-[10px] font-mono font-bold uppercase">
                {{ c.category }}
              </span>
              <h4 class="font-mono font-bold text-white text-sm">{{ c.title }}</h4>
            </div>
            <p class="text-xs text-slate-400 font-sans">{{ c.description }}</p>
            <div class="mt-2 bg-[#050811] border border-slate-800 p-2 rounded font-mono text-xs text-emerald-400 overflow-x-auto">
              <code>{{ c.command }}</code>
            </div>
          </div>

          <button
            @click="copyText(c.command)"
            class="self-start md:self-center px-3 py-1.5 rounded bg-slate-800 hover:bg-cyan-500 hover:text-slate-950 text-cyan-400 border border-slate-700 text-xs font-mono font-semibold transition-colors whitespace-nowrap"
          >
            Copiar Comando
          </button>
        </div>
      </div>
    </div>

    <!-- TAB 3: PLAYBOOKS DE HABILIDADES -->
    <div v-if="activeTab === 'skills'" class="space-y-4">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
        <!-- Lista de Skills -->
        <div class="tactical-card space-y-2 p-3">
          <h3 class="text-xs font-mono font-bold text-white uppercase tracking-wider mb-2">Playbooks en skills/</h3>
          <button
            v-for="s in skills"
            :key="s.id"
            @click="selectSkill(s.id)"
            class="w-full text-left p-2.5 rounded font-mono text-xs transition-colors flex items-center justify-between"
            :class="selectedSkillId === s.id ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/40' : 'text-slate-300 hover:bg-slate-800/60'"
          >
            <span class="truncate font-semibold">{{ s.id }}</span>
            <span class="text-[10px] text-slate-500">&rarr;</span>
          </button>
        </div>

        <!-- Visor del Playbook -->
        <div class="md:col-span-2 tactical-card font-mono text-xs text-slate-200 max-h-[700px] overflow-y-auto space-y-3">
          <h3 class="text-sm font-bold text-cyan-400 pb-2 border-b border-slate-800">
            {{ selectedSkillId ? selectedSkillId : 'Selecciona un Playbook' }}
          </h3>
          <pre class="whitespace-pre-wrap leading-relaxed">{{ skillContent }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'

const activeTab = ref('access')
const cheatsheet = ref([])
const cheatQuery = ref('')
const skills = ref([])
const selectedSkillId = ref('')
const skillContent = ref('Selecciona un playbook para ver las instrucciones y playbooks técnicos.')

const filteredCheats = computed(() => {
  if (!cheatQuery.value.trim()) return cheatsheet.value
  const q = cheatQuery.value.toLowerCase()
  return cheatsheet.value.filter(c => {
    return c.title.toLowerCase().includes(q) ||
      c.command.toLowerCase().includes(q) ||
      c.description.toLowerCase().includes(q) ||
      c.category.toLowerCase().includes(q)
  })
})

async function loadCheatsheet() {
  try {
    cheatsheet.value = await api.getCheatsheet()
  } catch (err) {
    console.error('Error al cargar cheatsheet:', err)
  }
}

async function loadSkills() {
  try {
    skills.value = await api.getSkills()
    if (skills.value.length > 0 && !selectedSkillId.value) {
      selectSkill(skills.value[0].id)
    }
  } catch (err) {
    console.error('Error al cargar skills:', err)
  }
}

async function selectSkill(id) {
  selectedSkillId.value = id
  skillContent.value = 'Cargando contenido...'
  try {
    const res = await api.getSkillDetail(id)
    skillContent.value = res.content
  } catch (err) {
    skillContent.value = 'Error al cargar skill: ' + err.message
  }
}

function copyText(text) {
  navigator.clipboard.writeText(text)
  alert('Copiado al portapapeles: ' + text)
}

onMounted(() => {
  loadCheatsheet()
  loadSkills()
})
</script>
