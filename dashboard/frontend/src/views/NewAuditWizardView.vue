<template>
  <div class="max-w-3xl mx-auto space-y-6">
    <div class="flex items-center justify-between border-b border-[#1b253b] pb-4">
      <div>
        <h1 class="text-lg font-mono font-bold text-white flex items-center space-x-2">
          <span>🧭 Asistente Guiado: Nueva Auditoría</span>
        </h1>
        <p class="text-xs text-slate-400 mt-1">Crea el proyecto, define su alcance y lanza el primer reconocimiento en un solo flujo.</p>
      </div>
      <router-link to="/engagements" class="text-xs font-mono text-slate-400 hover:text-white">Cancelar y volver</router-link>
    </div>

    <!-- Indicador de pasos -->
    <div class="flex items-center space-x-2 text-xs font-mono">
      <div
        v-for="(label, idx) in ['Datos básicos', 'Alcance', 'Reconocimiento']"
        :key="label"
        class="flex items-center space-x-2"
      >
        <div
          class="w-6 h-6 rounded-full flex items-center justify-center border"
          :class="step === idx + 1
            ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
            : step > idx + 1
              ? 'bg-emerald-950 border-emerald-500/50 text-emerald-400'
              : 'bg-slate-900 border-slate-700 text-slate-500'"
        >
          {{ step > idx + 1 ? '✓' : idx + 1 }}
        </div>
        <span :class="step === idx + 1 ? 'text-cyan-300' : 'text-slate-500'">{{ label }}</span>
        <span v-if="idx < 2" class="text-slate-700">—</span>
      </div>
    </div>

    <!-- Paso 1: Datos básicos -->
    <div v-if="step === 1" class="tactical-card space-y-4">
      <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider border-b border-slate-800 pb-2">Paso 1 · Datos básicos</h2>
      <div>
        <label class="block text-xs font-mono text-slate-300 mb-1">Nombre del proyecto:</label>
        <input
          v-model="form.name"
          type="text"
          required
          placeholder="acme-corp"
          class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
        />
      </div>
      <div>
        <label class="block text-xs font-mono text-slate-300 mb-1">Dominio objetivo (opcional):</label>
        <input
          v-model="form.domain"
          type="text"
          placeholder="target.local"
          class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
        />
      </div>
      <div>
        <label class="block text-xs font-mono text-slate-300 mb-1">Cliente u organización (opcional):</label>
        <input
          v-model="form.client"
          type="text"
          placeholder="Acme Corp"
          class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
        />
      </div>
      <p v-if="errorMsg" class="text-xs font-mono text-rose-400">{{ errorMsg }}</p>
      <button
        type="button"
        :disabled="!form.name.trim() || isSubmitting"
        @click="submitStep1"
        class="w-full py-2 rounded-sm bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-slate-950 text-sm font-mono font-bold"
      >
        {{ isSubmitting ? 'Creando proyecto...' : 'Crear y continuar →' }}
      </button>
    </div>

    <!-- Paso 2: Alcance -->
    <div v-if="step === 2" class="tactical-card space-y-4">
      <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider border-b border-slate-800 pb-2 flex items-center">
        <span>Paso 2 · Alcance</span>
        <HelpTooltip label="Alcance">Solo lo que escribas aquí (y sus subdominios si usas *.) queda autorizado para el reconocimiento automático. Puedes ajustarlo después desde el detalle del proyecto.</HelpTooltip>
      </h2>
      <div>
        <label class="block text-xs font-mono text-slate-300 mb-1">Dominios / Wildcards autorizados (uno por línea):</label>
        <textarea
          v-model="scopeForm.domains"
          rows="3"
          placeholder="target.local&#10;*.target.local"
          class="w-full bg-[#070b14] border border-slate-800 focus:border-cyan-400 rounded-sm p-2 text-slate-200 font-mono text-xs focus:outline-hidden"
        ></textarea>
      </div>
      <div>
        <label class="block text-xs font-mono text-slate-300 mb-1">IPs y CIDRs autorizados (opcional, uno por línea):</label>
        <textarea
          v-model="scopeForm.ips"
          rows="2"
          placeholder="192.168.1.10&#10;10.0.0.0/24"
          class="w-full bg-[#070b14] border border-slate-800 focus:border-cyan-400 rounded-sm p-2 text-slate-200 font-mono text-xs focus:outline-hidden"
        ></textarea>
      </div>
      <div>
        <label class="block text-xs text-slate-300 mb-1">Dominios excluidos (uno por línea):</label>
        <textarea v-model="scopeForm.exclusions" rows="2" placeholder="Solo exclusiones reales del permiso de auditoría" class="w-full bg-[#070b14] border border-slate-800 rounded-sm p-2 text-xs text-slate-200"></textarea>
      </div>
      <label class="flex items-start gap-2 text-xs text-slate-300">
        <input v-model="scopeConfirmed" type="checkbox" data-testid="confirm-scope" />
        <span>Confirmo que estos activos están autorizados. Un dominio no incluye sus subdominios: añade *.dominio únicamente si tienes permiso.</span>
      </label>
      <p v-if="errorMsg" class="text-xs font-mono text-rose-400">{{ errorMsg }}</p>
      <div class="flex items-center space-x-3">
        <button
          type="button"
          :disabled="isSubmitting || !scopeConfirmed"
          @click="submitStep2"
          class="flex-1 py-2 rounded-sm bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 text-sm font-mono font-bold"
        >
          {{ isSubmitting ? 'Guardando...' : 'Guardar y continuar →' }}
        </button>
        <button
          type="button"
          :disabled="isSubmitting"
          @click="goToDetail"
          class="py-2 px-3 rounded-sm border border-slate-700 text-slate-300 hover:bg-slate-800 text-xs font-mono"
        >
          Guardar proyecto y revisar después
        </button>
      </div>
    </div>

    <!-- Paso 3: Primer reconocimiento -->
    <div v-if="step === 3" class="tactical-card space-y-4">
      <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider border-b border-slate-800 pb-2">Paso 3 · Primer reconocimiento</h2>
      <p class="text-xs text-slate-400">
        Ejecuta subdominios, sondeo web, cosecha de URLs y patrones de riesgo sobre el alcance que acabas de definir, respetando Scope Guard. Puedes repetirlo cuando quieras desde el detalle del proyecto.
      </p>
      <label class="flex items-center space-x-2 text-xs font-mono text-slate-300">
        <input type="checkbox" v-model="dryRun" class="rounded-sm bg-slate-900 border-slate-700 text-cyan-500 focus:ring-cyan-500" />
        <span>Modo Dry-Run (simula sin tocar la red; recomendado para la primera vez)</span>
      </label>
      <p v-if="errorMsg" class="text-xs font-mono text-rose-400">{{ errorMsg }}</p>
      <div class="flex items-center space-x-3">
        <button
          type="button"
          :disabled="isSubmitting"
          @click="submitStep3"
          class="flex-1 py-2 rounded-sm bg-linear-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50 text-slate-950 text-sm font-mono font-bold"
        >
          {{ isSubmitting ? 'Lanzando...' : '🚀 Lanzar reconocimiento' }}
        </button>
        <button
          type="button"
          :disabled="isSubmitting"
          @click="goToDetail"
          class="py-2 px-3 rounded-sm border border-slate-700 text-slate-300 hover:bg-slate-800 text-xs font-mono"
        >
          Omitir, ir al detalle
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { splitIpsAndCidrs } from '../scope-utils'
import HelpTooltip from '../components/HelpTooltip.vue'

// Fase 113 / backlog A9: encadena crear proyecto -> definir alcance ->
// lanzar el primer recon en un solo flujo guiado, para que un operador
// no experimentado no tenga que descubrir por su cuenta que son 3 pasos
// separados en engagements/scope/recon.

const router = useRouter()

const step = ref(1)
const isSubmitting = ref(false)
const errorMsg = ref('')

const form = ref({ name: '', domain: '', client: '' })
const scopeForm = ref({ domains: '', ips: '', exclusions: '' })
const scopeConfirmed = ref(false)
const dryRun = ref(true)

const created = ref(null) // { id, type }

async function submitStep1() {
  if (!form.value.name.trim()) return
  isSubmitting.value = true
  errorMsg.value = ''
  try {
    created.value = await api.createEngagement({
      name: form.value.name.trim(),
      type: 'engagement',
      domain: form.value.domain.trim(),
      client: form.value.client.trim(),
    })
    // Precarga el dominio tecleado en el paso 1 como punto de partida del
    // alcance, para no pedirlo dos veces.
    if (form.value.domain.trim()) {
      const target = form.value.domain.trim()
      if (target.includes(':') || /^\d+\.\d+\.\d+\.\d+$/.test(target)) scopeForm.value.ips = target
      else scopeForm.value.domains = target
    }
    step.value = 2
  } catch (err) {
    errorMsg.value = err.message || 'No se pudo crear el proyecto'
  } finally {
    isSubmitting.value = false
  }
}

async function submitStep2() {
  if (!scopeConfirmed.value) return
  isSubmitting.value = true
  errorMsg.value = ''
  try {
    const current = await api.getScope(created.value.id, created.value.type)
    const existingInScope = current.scope?.in_scope || {}
    const existingOutScope = current.scope?.out_of_scope || {}
    const { ips, cidrs } = splitIpsAndCidrs(scopeForm.value.ips)
    const domains = scopeForm.value.domains.split('\n').map(s => s.trim()).filter(Boolean)
    if (!domains.length && !ips.length && !cidrs.length && !existingInScope.endpoints?.length) {
      throw new Error('Indica al menos un dominio, IP o rango autorizado antes de continuar.')
    }
    await api.updateScope(created.value.id, {
      ...current,
      scope: {
        in_scope: {
          domains,
          ips,
          cidrs,
          endpoints: existingInScope.endpoints || [],
        },
        out_of_scope: { ...existingOutScope, domains: scopeForm.value.exclusions.split('\n').map(s => s.trim()).filter(Boolean) },
      },
    }, created.value.type)
    step.value = 3
  } catch (err) {
    errorMsg.value = err.message || 'No se pudo guardar el alcance'
  } finally {
    isSubmitting.value = false
  }
}

async function submitStep3() {
  isSubmitting.value = true
  errorMsg.value = ''
  try {
    await api.runRecon(created.value.id, { stage: 'all', dry_run: dryRun.value }, created.value.type)
    goToDetail()
  } catch (err) {
    errorMsg.value = err.message || 'No se pudo iniciar el reconocimiento'
    isSubmitting.value = false
  }
}

function goToDetail() {
  router.push(`/engagements/${created.value.type}/${created.value.id}`)
}
</script>
