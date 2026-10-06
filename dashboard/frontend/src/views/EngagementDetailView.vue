<template>
  <div class="space-y-6">
    <!-- Breadcrumb y Header -->
    <div class="no-print flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1b253b] pb-4">
      <div>
        <div class="flex items-center space-x-2 text-xs font-mono text-slate-400 mb-1">
          <router-link to="/engagements" class="hover:text-cyan-400">&larr; Auditorías</router-link>
          <span>/</span>
          <span class="text-cyan-400">{{ engId }}</span>
          <span class="px-1.5 py-0.2 rounded-sm bg-slate-800 text-[10px] text-slate-300 uppercase">
            {{ engType }}
          </span>
        </div>
        <h1 class="text-2xl font-mono font-bold text-white flex items-center space-x-3 flex-wrap gap-2">
          <span>{{ engId }}</span>
          <span class="text-xs px-2 py-0.5 rounded-sm font-normal font-mono" :class="hasScope ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'">
            {{ hasScope ? 'Alcance Definido' : 'target.yaml pendiente' }}
          </span>
          <span v-if="engType === 'reto' && flagsData.subtype === 'jeopardy' && flagsData.category"
            class="text-xs px-2 py-0.5 rounded-sm font-normal font-mono uppercase"
            :class="getCategoryBadgeClass(flagsData.category)">
            {{ flagsData.category }}
          </span>
          <span v-if="engType === 'reto' && flagsData.points"
            class="text-xs px-2 py-0.5 rounded-sm font-normal font-mono bg-amber-500/10 text-amber-300 border border-amber-500/30">
            {{ flagsData.points }} pts
          </span>
          <span v-if="engType === 'reto' && isProjectSolved"
            class="text-xs px-2 py-0.5 rounded-sm font-normal font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
            ✓ RESUELTO
          </span>
        </h1>
      </div>

      <!-- Acciones de Cabecera -->
      <div class="flex flex-wrap items-center gap-3 text-xs font-mono">
        <DeleteProjectButton :project-id="engId" :project-type="engType" @deleted="router.push('/engagements')" />
        <button
          @click="compileReportAction"
          :disabled="isCompiling"
          class="px-3 py-1.5 rounded-sm bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-bold transition-all shadow-xs flex items-center space-x-1"
        >
          <span>📄</span>
          <span>{{ isCompiling ? 'Compilando...' : 'Compilar Reporte' }}</span>
        </button>

        <button
          @click="packEngagementAction"
          :disabled="isPacking"
          class="px-3 py-1.5 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all flex items-center space-x-1 cursor-pointer"
        >
          <span>📦</span>
          <span>{{ isPacking ? 'Empaquetando...' : 'Empaquetar y Descargar (.tar.gz)' }}</span>
        </button>
      </div>
    </div>

    <!-- Navegación por Pestañas Tácticas -->
    <div class="no-print flex items-center space-x-1 border-b border-[#1b253b] text-xs font-mono overflow-x-auto pb-1">
      <button
        v-for="t in tabs"
        :key="t.id"
        @click="activeTab = t.id"
        class="px-4 py-2 rounded-t font-semibold transition-all whitespace-nowrap flex items-center space-x-2 border-b-2"
        :class="activeTab === t.id ? 'border-cyan-400 text-cyan-400 bg-cyan-950/20' : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'"
      >
        <span>{{ t.icon }}</span>
        <span>{{ t.label }}</span>
        <span v-if="t.count !== undefined" class="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300">
          {{ t.count }}
        </span>
      </button>
    </div>

    <!-- Contenido de Pestañas -->

    <!-- TAB 1: ALCANCE & SCOPE GUARD -->
    <div v-if="activeTab === 'scope'" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Editor In-Scope & Out-of-Scope -->
        <div class="lg:col-span-2 tactical-card space-y-5">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <span>🎯 Reglas de Alcance (target.yaml)</span>
            </h2>
            <button
              @click="saveScopeConfig"
              :disabled="isSavingScope"
              class="px-3 py-1 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-xs font-mono font-bold"
            >
              {{ isSavingScope ? 'Guardando...' : 'Guardar Alcance' }}
            </button>
          </div>

          <!-- In-Scope -->
          <div class="space-y-3">
            <h3 class="text-xs font-mono font-bold text-emerald-400 uppercase tracking-wider flex items-center space-x-1">
              <span>✓ Activos Dentro de Alcance (In-Scope)</span>
            </h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
              <div>
                <label class="text-slate-400 block mb-1">Dominios / Wildcards (uno por línea):</label>
                <textarea
                  v-model="inScopeDomainsText"
                  rows="4"
                  class="w-full bg-[#070b14] border border-slate-800 focus:border-cyan-400 rounded-sm p-2 text-slate-200 font-mono text-xs focus:outline-hidden"
                  placeholder="target.local&#10;*.target.local"
                ></textarea>
              </div>
              <div>
                <label class="text-slate-400 block mb-1">IPs y CIDRs autorizados:</label>
                <textarea
                  v-model="inScopeIpsText"
                  rows="4"
                  class="w-full bg-[#070b14] border border-slate-800 focus:border-cyan-400 rounded-sm p-2 text-slate-200 font-mono text-xs focus:outline-hidden"
                  placeholder="192.168.1.10&#10;10.0.0.0/24"
                ></textarea>
              </div>
            </div>
          </div>

          <!-- Out-of-Scope -->
          <div class="space-y-3 pt-3 border-t border-slate-800">
            <h3 class="text-xs font-mono font-bold text-red-400 uppercase tracking-wider flex items-center space-x-1">
              <span>🚫 Exclusiones Críticas (Out-of-Scope)</span>
            </h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
              <div>
                <label class="text-slate-400 block mb-1">Dominios o Hosts Excluidos:</label>
                <textarea
                  v-model="outScopeDomainsText"
                  rows="3"
                  class="w-full bg-[#070b14] border border-slate-800 focus:border-red-400 rounded-sm p-2 text-slate-200 font-mono text-xs focus:outline-hidden"
                  placeholder="payments.target.local&#10;status.target.local"
                ></textarea>
              </div>
              <div>
                <label class="text-slate-400 block mb-1">Notas de Exclusión:</label>
                <textarea
                  v-model="outScopeNotesText"
                  rows="3"
                  class="w-full bg-[#070b14] border border-slate-800 focus:border-red-400 rounded-sm p-2 text-slate-200 font-mono text-xs focus:outline-hidden"
                  placeholder="Prohibido pruebas de denegación de servicio&#10;Terceros fuera de alcance"
                ></textarea>
              </div>
            </div>
          </div>
        </div>

        <!-- Scope Guard Tester & Límites -->
        <div class="space-y-5">
          <div class="tactical-card space-y-4">
            <h3 class="text-sm font-mono font-bold text-white uppercase tracking-wider border-b border-slate-800 pb-2">
              <span>⚡ Probar con pt-scope</span>
            </h3>
            <div class="space-y-2">
              <input
                v-model="scopeTestInput"
                type="text"
                placeholder="host.target.local"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
              />
              <button
                @click="testScope"
                class="w-full py-1.5 rounded-sm bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-mono font-bold text-xs"
              >
                Ejecutar Scope Guard
              </button>
            </div>

            <div v-if="scopeTestResult" class="p-3 rounded-sm border text-xs font-mono" :class="scopeTestResult.allowed ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300' : 'bg-red-950/40 border-red-500/40 text-red-300'">
              <div class="font-bold">{{ scopeTestResult.status }}</div>
              <div class="mt-1">{{ scopeTestResult.reason }}</div>
            </div>
          </div>

          <div class="tactical-card space-y-3 text-xs font-mono text-slate-300">
            <h3 class="font-bold text-white uppercase tracking-wider border-b border-slate-800 pb-2">
              Límites Operacionales
            </h3>
            <div class="flex justify-between py-1 border-b border-slate-800/60">
              <span class="text-slate-400">Peticiones / seg:</span>
              <span class="text-cyan-300">{{ scopeData.operational_limits?.max_requests_per_second || 1 }} req/s</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-800/60">
              <span class="text-slate-400">Hilos concurrentes:</span>
              <span class="text-cyan-300">{{ scopeData.operational_limits?.max_parallel_threads || 1 }} threads</span>
            </div>
            <div class="flex justify-between py-1">
              <span class="text-slate-400">DoS permitido:</span>
              <span class="text-red-400 font-bold">{{ scopeData.operational_limits?.dos_testing ? 'SÍ' : 'NO' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB: RECONOCIMIENTO & SCOPE GUARD -->
    <div v-if="activeTab === 'recon'" class="space-y-6">
      <!-- Fila Superior: Resumen de Alcance & Tarjeta Lanzadora -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Lanzador del Pipeline -->
        <div class="lg:col-span-2 tactical-card space-y-4">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider flex items-center space-x-2">
                <span>📡 Pipeline de Reconocimiento Táctico</span>
              </h2>
              <p class="text-xs text-slate-400">Automatización pasiva y activa asistida por Scope Guard (pt-recon-pipeline)</p>
            </div>
            <span
              class="px-2 py-0.5 rounded-sm text-xs font-mono font-bold"
              :class="reconIsRunning ? 'bg-cyan-950 text-cyan-400 border border-cyan-500/50 animate-pulse' : 'bg-slate-800 text-slate-400'"
            >
              {{ reconJobLabel }}
            </span>
          </div>

          <!-- Selector de Etapa y Opciones -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
            <div>
              <label class="text-slate-400 block mb-1">Etapa de Reconocimiento:</label>
              <select
                v-model="reconStage"
                :disabled="reconIsRunning"
                class="w-full bg-[#070b14] border border-slate-800 focus:border-cyan-400 rounded-sm p-2 text-slate-200 focus:outline-hidden"
              >
                <option value="all">Completo (Todas las etapas)</option>
                <option value="subdomains">1. Subdominios (subfinder, assetfinder, findomain)</option>
                <option value="probe">2. Sondeo Web (HTTP/HTTPS controlado)</option>
                <option value="urls">3. Cosecha de URLs y JS (gau)</option>
                <option value="patterns">4. Patrones de Riesgo (gf)</option>
              </select>
            </div>

            <div>
              <label class="text-slate-400 block mb-1">Modo de Ejecución:</label>
              <div class="flex items-center space-x-2 pt-2">
                <input
                  type="checkbox"
                  id="recon-dry-run"
                  v-model="reconDryRun"
                  :disabled="reconIsRunning"
                  class="rounded-sm bg-slate-900 border-slate-700 text-cyan-500 focus:ring-cyan-500"
                />
                <label for="recon-dry-run" class="text-slate-300 cursor-pointer">
                  Modo Dry-Run (Simulación)
                </label>
              </div>
            </div>

            <div class="flex items-end">
              <button
                @click="triggerReconPipeline"
                :disabled="reconIsRunning || isStartingRecon"
                class="w-full py-2 px-3 rounded-sm font-mono font-bold text-xs transition-all flex items-center justify-center space-x-2 shadow-lg cursor-pointer"
                :class="reconIsRunning ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-linear-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 shadow-cyan-500/20'"
              >
                <span v-if="reconIsRunning" class="animate-spin">⚙️</span>
                <span v-else>🚀</span>
                <span>{{ reconIsRunning ? 'Reconocimiento en curso...' : 'Iniciar Reconocimiento' }}</span>
              </button>
            </div>
          </div>

          <!-- Mensaje / Feedback de Lanzamiento -->
          <button v-if="reconIsRunning" @click="cancelReconPipeline"
            :disabled="isCancellingRecon || reconStatus.job?.status === 'cancelling'"
            class="mt-3 w-full rounded-sm border border-rose-500/50 bg-rose-950/50 px-4 py-2 text-sm font-mono text-rose-300 disabled:opacity-50">
            {{ reconStatus.job?.status === 'cancelling' ? 'Cancelando reconocimiento...' : 'Cancelar reconocimiento' }}
          </button>
          <p v-if="reconStatus.job?.started_at" class="mt-2 text-xs text-slate-400 font-mono">
            Inicio: {{ new Date(reconStatus.job.started_at).toLocaleString() }}
            <span v-if="reconStatus.job?.finished_at"> · Fin: {{ new Date(reconStatus.job.finished_at).toLocaleString() }}</span>
          </p>
          <div v-if="reconActionMsg" class="p-2.5 rounded-sm text-xs font-mono border" :class="reconActionSuccess ? 'bg-cyan-950/40 border-cyan-500/30 text-cyan-300' : 'bg-rose-950/40 border-rose-500/30 text-rose-300'">
            {{ reconActionMsg }}
          </div>
        </div>

        <!-- Scope Guard Card -->
        <div class="tactical-card space-y-3">
          <h3 class="text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider flex items-center space-x-1.5">
            <span>🛡️ Scope Guard Activo</span>
          </h3>
          <p class="text-[11px] text-slate-400 font-mono">
            El sondeo valida alcance y DNS antes de conectar. No sigue redirecciones. Un dominio exacto no incluye subdominios; *.example.com no incluye example.com.
          </p>
          <p class="text-[11px] text-slate-400 font-mono">
            HTTP activo: límites de target.yaml; por defecto 1 intento/s y 1 tarea. Las consultas pasivas a proveedores usan los controles de cada herramienta.
          </p>
          <p v-if="reconStatus.summary?.operational_limits" class="text-[11px] text-cyan-300 font-mono">
            Última ejecución: {{ reconStatus.summary.operational_limits.max_requests_per_second }} intentos/s;
            {{ reconStatus.summary.operational_limits.max_parallel_threads }} tareas;
            máximo {{ reconStatus.summary.operational_limits.max_probe_targets }} destinos.
          </p>
          <div class="space-y-1.5 text-xs font-mono bg-[#070b14] p-3 rounded-sm border border-slate-800">
            <div class="text-slate-400 text-[10px] uppercase">Dominios Autorizados:</div>
            <div v-if="reconStatus.configured_domains && reconStatus.configured_domains.length" class="flex flex-wrap gap-1">
              <span v-for="d in reconStatus.configured_domains" :key="d" class="px-2 py-0.5 rounded-sm bg-emerald-950/70 border border-emerald-500/40 text-emerald-300 text-[11px]">
                {{ d }}
              </span>
            </div>
            <div v-else class="text-amber-400 text-[11px]">
              ⚠️ No hay dominios base definidos en in_scope.domains
            </div>
          </div>
        </div>
      </div>

      <div v-if="reconStatus.job?.status === 'failed' || reconStatus.summary?.status === 'failed'" class="p-3 rounded-sm border border-rose-500/40 bg-rose-950/30 text-rose-300 text-xs font-mono" role="alert">
        El reconocimiento falló. Consulta la consola para ver la causa. Las métricas pueden incluir archivos de ejecuciones anteriores; no confirman una ejecución completa.
        <p v-if="reconStatus.job?.error" class="mt-1">{{ reconStatus.job.error }}</p>
      </div>
      <div v-if="['interrupted', 'cancelled', 'cancelling'].includes(reconStatus.job?.status)"
        class="p-3 rounded-sm border border-amber-500/40 bg-amber-950/30 text-amber-300 text-xs font-mono" role="status">
        {{ reconStatus.job?.status === 'interrupted' ? 'Ejecución interrumpida por un reinicio. No se reanudó automáticamente.' : reconStatus.job?.status === 'cancelling' ? 'Cancelación en curso. Espera a que termine antes de iniciar otra ejecución.' : 'Reconocimiento cancelado.' }}
        Los archivos previos se conservan y pueden contener resultados parciales; no confirman una ejecución completa.
      </div>
      <div v-if="reconStatus.job?.status === 'simulated'" class="p-3 rounded-sm border border-cyan-500/40 bg-cyan-950/30 text-cyan-300 text-xs font-mono" role="status">
        Simulación finalizada sin consultas de red. No se generaron resultados de reconocimiento. Las métricas muestran los archivos que ya existían.
      </div>

      <!-- Métricas Clave de Reconocimiento -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 font-mono">
        <div class="p-4 rounded-lg bg-[#0d1322] border border-slate-800">
          <div class="text-[11px] text-slate-400 uppercase">Subdominios Autorizados</div>
          <div class="text-2xl font-bold text-cyan-400 mt-1">
            {{ reconStatus.summary?.subdomains_count || 0 }}
          </div>
          <div class="text-[10px] text-slate-500 mt-0.5">Guardados en recon/subdomains.txt</div>
        </div>

        <div class="p-4 rounded-lg bg-[#0d1322] border border-slate-800">
          <div class="text-[11px] text-slate-400 uppercase">Bloqueados por Scope</div>
          <div class="text-2xl font-bold mt-1" :class="(reconStatus.summary?.subdomains_discarded_out_of_scope || 0) > 0 ? 'text-amber-400' : 'text-slate-400'">
            {{ reconStatus.summary?.subdomains_discarded_out_of_scope || 0 }}
          </div>
          <div class="text-[10px] text-slate-500 mt-0.5">Filtrados antes del sondeo</div>
        </div>

        <div class="p-4 rounded-lg bg-[#0d1322] border border-slate-800">
          <div class="text-[11px] text-slate-400 uppercase">Servicios Web Activos</div>
          <div class="text-2xl font-bold text-emerald-400 mt-1">
            {{ reconStatus.summary?.live_hosts_count || 0 }}
          </div>
          <div class="text-[10px] text-slate-500 mt-0.5">live_hosts.txt (HTTP/HTTPS)</div>
        </div>

        <div class="p-4 rounded-lg bg-[#0d1322] border border-slate-800">
          <div class="text-[11px] text-slate-400 uppercase">URLs & JavaScript</div>
          <div class="text-2xl font-bold text-purple-400 mt-1">
            {{ reconStatus.summary?.urls_count || 0 }}
          </div>
          <div class="text-[10px] text-slate-500 mt-0.5">{{ reconStatus.summary?.js_files_count || 0 }} archivos JS cosechados</div>
        </div>
      </div>

      <!-- Patrones de Riesgo GF si existen -->
      <div v-if="reconStatus.summary?.gf_patterns && Object.keys(reconStatus.summary.gf_patterns).length" class="tactical-card space-y-3 font-mono">
        <h3 class="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center space-x-1.5">
          <span>🎯 Patrones de Riesgo Detectados (gf)</span>
        </h3>
        <div class="flex flex-wrap gap-2 text-xs">
          <div
            v-for="(count, pat) in reconStatus.summary.gf_patterns"
            :key="pat"
            class="px-2.5 py-1 rounded-sm bg-[#070b14] border border-slate-800 flex items-center space-x-2"
          >
            <span class="font-bold text-slate-300 uppercase">{{ pat }}</span>
            <span class="px-1.5 py-0.2 rounded-sm text-[10px] font-bold" :class="count > 0 ? 'bg-amber-950 text-amber-400 border border-amber-500/40' : 'bg-slate-800 text-slate-400'">
              {{ count }}
            </span>
          </div>
        </div>
      </div>

      <!-- Consola de Ejecución en Vivo & Descartados por Scope Guard -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 font-mono">
        <!-- Terminal Log en Vivo -->
        <div class="lg:col-span-2 tactical-card space-y-3">
          <div class="flex items-center justify-between border-b border-slate-800 pb-2">
            <span class="text-xs font-bold text-slate-300 flex items-center space-x-1.5">
              <span>🖥️ Bitácora de Reconocimiento (recon.log)</span>
            </span>
            <div class="flex items-center space-x-2">
              <button
                @click="loadReconLog"
                class="px-2 py-1 rounded-sm bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300 cursor-pointer"
              >
                Actualizar Log
              </button>
            </div>
          </div>
          <div class="bg-black/90 p-3 rounded-lg border border-slate-800 h-80 overflow-y-auto font-mono text-[11px] text-emerald-400 whitespace-pre leading-relaxed select-text">
            {{ reconLogContent || 'No hay registros recientes de reconocimiento. Inicie una ejecución arriba.' }}
          </div>
        </div>

        <!-- Tabla de Descartados por Scope Guard -->
        <div class="tactical-card space-y-3 font-mono">
          <div class="flex items-center justify-between border-b border-slate-800 pb-2">
            <span class="text-xs font-bold text-rose-400 flex items-center space-x-1.5">
              <span>🚫 Bloqueos Scope Guard</span>
            </span>
            <span class="text-[10px] text-slate-500">
              {{ reconStatus.discarded_out_of_scope?.length || 0 }} registros
            </span>
          </div>
          <div class="h-80 overflow-y-auto space-y-2 text-xs">
            <div
              v-for="(item, idx) in reconStatus.discarded_out_of_scope"
              :key="idx"
              class="p-2 rounded-sm bg-[#070b14] border border-rose-950/60 space-y-1"
            >
              <div class="text-rose-300 font-bold break-all">{{ item.target }}</div>
              <div class="text-[10px] text-slate-400">{{ item.reason }}</div>
            </div>
            <div v-if="!reconStatus.discarded_out_of_scope || reconStatus.discarded_out_of_scope.length === 0" class="text-center py-12 text-slate-500 text-xs">
              No se han detectado objetivos fuera de alcance.
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2: HALLAZGOS & EVIDENCIAS (Evidence-First) -->
    <div v-if="activeTab === 'findings'" class="space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-base font-mono font-bold text-white flex items-center space-x-2">
            <span>📋 Fichas de Hallazgo (Evidence-First)</span>
          </h2>
          <p class="text-xs text-slate-400">Almacenadas en /workspace/{{ engType === 'reto' ? 'retos' : 'engagements' }}/{{ engId }}/evidence/*.md</p>
        </div>

        <button
          @click="openNewFindingModal"
          class="px-4 py-2 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs shadow-md shadow-cyan-500/20"
        >
          + Nueva Ficha (pt-finding new)
        </button>
      </div>

      <div v-if="findings.length === 0" class="text-center py-16 tactical-card space-y-3">
        <div class="text-3xl">🛡️</div>
        <p class="text-slate-300 font-mono text-sm">No hay vulnerabilidades registradas aún en evidence/.</p>
        <button
          @click="openNewFindingModal"
          class="px-3 py-1.5 rounded-sm bg-cyan-600 text-slate-950 font-bold text-xs font-mono"
        >
          Crear Primer Hallazgo
        </button>
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div
          v-for="f in findings"
          :key="f.slug"
          class="tactical-card flex flex-col justify-between space-y-3"
        >
          <div>
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-2">
                <span
                  class="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold"
                  :class="getSeverityClass(f.frontmatter?.severity)"
                >
                  {{ f.frontmatter?.severity || 'MEDIUM' }}
                </span>
                <span
                  v-if="f.frontmatter?.status"
                  class="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold border"
                  :class="getFindingStatusClass(f.frontmatter?.status)"
                >
                  {{ f.frontmatter?.status }}
                </span>
              </div>
              <span class="text-xs font-mono text-cyan-400 font-bold">
                CVSS: {{ f.frontmatter?.cvss_score || 'N/A' }}
              </span>
            </div>

            <h3 class="text-base font-mono font-bold text-white mt-2">{{ f.frontmatter?.title }}</h3>
            <p class="text-xs font-mono text-slate-400 mt-0.5">
              <span>Activo: {{ f.frontmatter?.asset || 'No especificado' }}</span>
              <span v-if="f.frontmatter?.cwe" class="ml-2 text-slate-500">({{ f.frontmatter.cwe }})</span>
            </p>

            <div class="mt-3 text-xs text-slate-300 font-sans line-clamp-3 bg-slate-900/50 p-2.5 rounded-sm border border-slate-800">
              {{ f.body }}
            </div>
          </div>

          <div class="flex items-center justify-between pt-2 border-t border-slate-800 text-xs font-mono">
            <span class="text-slate-500">{{ f.filename }}</span>
            <div class="flex items-center space-x-2">
              <button
                @click="editFinding(f)"
                class="px-2 py-1 rounded-sm bg-slate-800 hover:bg-slate-700 text-cyan-400"
              >
                Editar
              </button>
              <button
                @click="deleteFindingAction(f.slug)"
                class="px-2 py-1 rounded-sm bg-red-950/40 hover:bg-red-900/60 text-red-400"
              >
                Eliminar
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 3: TERMINAL LIVE LOGS (pt-log streaming) -->
    <div v-if="activeTab === 'logs'" class="space-y-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-2 text-xs font-mono text-slate-400">
          <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span class="text-white font-bold">terminal.log (tmux pipe-pane)</span>
          <span>•</span>
          <span>Captura continua de comandos y respuestas</span>
        </div>

        <button
          @click="loadLogs"
          class="px-3 py-1 rounded-sm bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-mono border border-slate-700"
        >
          Refrescar Log
        </button>
      </div>

      <div class="bg-[#050811] border border-cyan-500/20 rounded-lg p-4 font-mono text-xs text-slate-200 h-[600px] overflow-y-auto space-y-1">
        <pre class="whitespace-pre-wrap leading-relaxed">{{ logContent }}</pre>
      </div>
    </div>

    <!-- TAB 4: METODOLOGÍA & COBERTURA (pt-checklist & pt-next) -->
    <div v-if="activeTab === 'checklist'" class="space-y-6">
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Cobertura de 8 Disciplinas -->
        <div class="lg:col-span-2 tactical-card space-y-4">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider">
              📊 Cobertura Metodológica de 8 Disciplinas (pt-checklist)
            </h2>
            <span class="text-sm font-mono font-bold text-cyan-400">
              {{ checklistData.coverage_pct || 0 }}% Cobertura
            </span>
          </div>

          <div v-if="checklistData.areas?.length > 0" class="space-y-3">
            <div
              v-for="area in checklistData.areas"
              :key="area.id"
              class="p-3 rounded-sm bg-slate-900/60 border border-slate-800 flex items-center justify-between"
            >
              <div>
                <span class="font-mono font-bold text-xs text-slate-200 block">{{ area.name }}</span>
                <span class="text-[11px] font-mono text-slate-400">{{ area.skill }}</span>
              </div>
              <span
                class="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold"
                :class="area.status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-slate-800 text-slate-400'"
              >
                {{ area.status }}
              </span>
            </div>
          </div>
          <div v-else class="text-slate-400 text-xs font-mono py-4">
            Ejecuta pruebas en terminal o documenta hallazgos para calcular la cobertura metodológica.
          </div>
        </div>

        <!-- Recomendación Próximo Paso (pt-next) -->
        <div class="tactical-card space-y-4">
          <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider border-b border-slate-800 pb-2">
            🧠 Asistente Táctico (pt-next)
          </h2>
          <div class="p-3 rounded-sm bg-slate-950 border border-cyan-500/30 text-xs font-mono text-cyan-300">
            {{ nextStepData.recommendation || 'Analizando estado del proyecto...' }}
          </div>
          <button
            @click="loadNextStepPrompt"
            class="w-full py-2 rounded-sm bg-slate-800 hover:bg-slate-700 text-cyan-400 border border-slate-700 text-xs font-mono font-bold"
          >
            Generar Prompt Táctico para Agente
          </button>
          <div v-if="agentPrompt" class="p-2.5 rounded-sm bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-300 max-h-48 overflow-y-auto">
            <pre class="whitespace-pre-wrap">{{ agentPrompt }}</pre>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB: COPILOTO TÁCTICO IA (pt-context + Tactical Proxy) -->
    <div v-if="activeTab === 'copilot'" class="space-y-6">
      <div class="tactical-card space-y-4">
        <!-- Barra de Configuración del Copiloto -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-800 gap-3">
          <div class="flex items-center space-x-3">
            <span class="text-2xl">🤖</span>
            <div>
              <h2 class="text-sm font-mono font-bold text-white">Copiloto Táctico de Auditoría (Evidence-First)</h2>
              <p class="text-xs text-slate-400">Contexto vivo inyectado automáticamente desde target.yaml, evidence/ y terminal.log.</p>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2 text-xs font-mono">
            <!-- Selector de Agente / Especialidad -->
            <select
              v-model="selectedAgent"
              class="bg-slate-900 border border-slate-700 rounded-sm px-2.5 py-1 text-cyan-300 focus:outline-hidden"
            >
              <option value="triage-agent">Triaje & Calidad (Gatekeeper)</option>
              <option value="recon-agent">Reconocimiento & Perfilado</option>
              <option value="auth-agent">Control de Acceso & Matriz Auth</option>
              <option value="logic-agent">Lógica de Negocio & Estados</option>
              <option value="injection-agent">Inyecciones & Callbacks</option>
              <option value="report-agent">Generación de Reportes</option>
              <option value="general">Copiloto General</option>
            </select>

            <!-- Selector de Modelo Inicial / Perfil LLM -->
            <select
              v-model="copilotSelectedModel"
              @change="onCopilotModelChange"
              class="bg-slate-900 border border-slate-700 rounded-sm px-2.5 py-1 text-cyan-300 focus:outline-hidden font-mono text-xs"
              title="Modelo o perfil inicial para la auditoría"
            >
              <option v-if="copilotSelectedModel.startsWith('openrouter:') && !copilotModels.some(m => `openrouter:${m.id}` === copilotSelectedModel)" :value="copilotSelectedModel">{{ copilotSelectedModel }} (fuera del catálogo)</option>
              <optgroup label="Modelos de tu cuenta OpenRouter">
                <option v-for="model in copilotModels" :key="model.id" :value="`openrouter:${model.id}`">{{ model.name }} — {{ model.id }}</option>
              </optgroup>
              <optgroup label="⚡ Perfiles Tácticos">
                <option value="profile:quick">Flash / Mini (Rápido)</option>
                <option value="profile:deep">Sonnet / GPT-4o (Profundo)</option>
                <option value="profile:local">Local / Ollama</option>
              </optgroup>
            </select>

            <span v-if="copilotModelsError" role="alert" class="text-xs text-red-400">{{ copilotModelsError }}</span>
            <!-- Botón Inspeccionar Contexto -->
            <button
              @click="openContextInspection"
              class="px-2.5 py-1 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-[11px]"
            >
              Ver Contexto pt-context
            </button>
          </div>
        </div>

        <!-- Prompts Rápidos Sugeridos -->
        <div class="flex flex-wrap gap-2 text-[11px] font-mono">
          <button
            v-for="(p, idx) in [
              'Evalúa si las evidencias registradas cumplen con el criterio Evidence-First.',
              '¿Cuál es la siguiente disciplina táctica recomendada para este objetivo?',
              'Redacta el impacto técnico y recomendación para el último hallazgo.',
              'Analiza los endpoints en target.yaml y sugiere vectores de prueba.'
            ]"
            :key="idx"
            @click="useQuickPrompt(p)"
            class="px-2.5 py-1 rounded-full bg-slate-900/90 border border-slate-800 hover:border-cyan-500/40 text-slate-300 hover:text-cyan-300 transition-colors"
          >
            {{ p }}
          </button>
        </div>

        <!-- Ventana de Chat de Conversación -->
        <div class="h-[480px] bg-[#050811] border border-slate-800 rounded-lg p-4 overflow-y-auto space-y-4 font-mono text-xs">
          <div v-if="copilotMessages.length === 0" class="text-center py-20 text-slate-500 space-y-2">
            <span class="text-3xl block">⚡</span>
            <p>El Copiloto Táctico está listo. Selecciona una pregunta rápida o escribe un mensaje abajo.</p>
            <p class="text-[10px] text-slate-600">Tiene acceso al alcance, evidencias validadas y checklist en tiempo real.</p>
          </div>

          <div
            v-for="(m, i) in copilotMessages"
            :key="i"
            class="flex flex-col space-y-1"
            :class="m.role === 'user' ? 'items-end' : 'items-start'"
          >
            <div class="flex items-center space-x-2 text-[10px] text-slate-500 font-bold uppercase">
              <span>{{ m.role === 'user' ? 'OPERADOR AUDITOR' : `COPILOTO (${m.model || 'AI'})` }}</span>
              <span v-if="m.latency_ms">({{ m.latency_ms }} ms)</span>
            </div>
            <div
              class="max-w-[85%] rounded-lg p-3 text-xs leading-relaxed"
              :class="m.role === 'user' ? 'bg-cyan-950/80 border border-cyan-500/40 text-cyan-100' : 'bg-slate-900 border border-slate-800 text-slate-200'"
            >
              <pre class="whitespace-pre-wrap font-mono">{{ m.content }}</pre>
            </div>
          </div>

          <div v-if="isCopilotThinking" class="flex items-center space-x-2 text-cyan-400 text-xs font-mono py-2 animate-pulse">
            <span>●</span>
            <span>Analizando evidencias y generando respuesta...</span>
          </div>
        </div>

        <!-- Input de Mensaje -->
        <form @submit.prevent="sendCopilotMessage" class="flex items-center gap-2">
          <input
            v-model="copilotInput"
            type="text"
            placeholder="Pregunta al copiloto sobre el alcance, metodología, o redacción de hallazgos..."
            class="flex-1 bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-lg px-4 py-2.5 text-xs font-mono text-slate-100 placeholder-slate-500 focus:outline-hidden"
            :disabled="isCopilotThinking"
          />
          <button
            type="submit"
            :disabled="isCopilotThinking || !copilotInput.trim()"
            class="px-5 py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold text-xs font-mono transition-all shadow-md shadow-cyan-500/20 whitespace-nowrap"
          >
            Enviar Consulta
          </button>
        </form>
      </div>

      <!-- Modal Inspección de Contexto pt-context -->
      <div
        v-if="showContextModal"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 overflow-y-auto"
      >
        <div class="bg-[#0d1322] border border-cyan-500/40 rounded-lg max-w-3xl w-full p-6 shadow-2xl space-y-4 my-8 max-h-[85vh] overflow-y-auto">
          <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 class="text-sm font-mono font-bold text-white flex items-center space-x-2">
              <span>📋 Contexto Vivo Inyectado (pt-agent-context)</span>
            </h2>
            <button @click="showContextModal = false" class="text-slate-400 hover:text-white font-mono text-lg">&times;</button>
          </div>
          <div class="bg-[#050811] p-4 rounded-sm border border-slate-800 text-xs font-mono text-slate-300 max-h-[500px] overflow-y-auto">
            <pre class="whitespace-pre-wrap">{{ injectedContextText }}</pre>
          </div>
          <div class="flex justify-end">
            <button
              @click="showContextModal = false"
              class="px-4 py-1.5 rounded-sm bg-slate-800 text-slate-300 text-xs font-mono"
            >
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 5: NOTAS DE TRABAJO (notes.md) -->
    <div v-if="activeTab === 'notes'" class="space-y-4">
      <div class="flex items-center justify-between">
        <span class="text-xs font-mono text-slate-400">notes.md en /workspace/{{ engType }}/{{ engId }}</span>
        <button
          @click="saveNotes"
          :disabled="isSavingNotes"
          class="px-3 py-1.5 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono font-bold text-xs"
        >
          {{ isSavingNotes ? 'Guardando...' : 'Guardar Notas' }}
        </button>
      </div>
      <textarea
        v-model="notesContent"
        rows="20"
        class="w-full bg-[#070b14] border border-[#1b253b] focus:border-cyan-400 rounded-lg p-4 font-mono text-xs text-slate-200 focus:outline-hidden"
      ></textarea>
    </div>

    <!-- TAB 6: VISTA PREVIA DEL INFORME (REPORT.md) & VISTA EJECUTIVA -->
    <div v-if="activeTab === 'report'" class="space-y-6">
      <!-- Barra de Acciones del Reporte (no se imprime) -->
      <div class="no-print flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#0d1322] border border-[#1b253b] p-4 rounded-lg">
        <div class="flex items-center space-x-2 text-xs font-mono">
          <span class="text-slate-400">Modo:</span>
          <button
            @click="reportViewMode = 'executive'"
            class="px-3 py-1.5 rounded-sm transition-colors flex items-center space-x-1.5"
            :class="reportViewMode === 'executive' ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 font-bold' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'"
          >
            <span>👔</span>
            <span>Vista Ejecutiva</span>
          </button>
          <button
            @click="reportViewMode = 'markdown'"
            class="px-3 py-1.5 rounded-sm transition-colors flex items-center space-x-1.5"
            :class="reportViewMode === 'markdown' ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40 font-bold' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'"
          >
            <span>📝</span>
            <span>Markdown Fuente</span>
          </button>
        </div>

        <div class="flex items-center space-x-2 text-xs font-mono">
          <button
            @click="compileReportAction"
            :disabled="isCompiling"
            class="px-3 py-1.5 rounded-sm bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 font-bold transition-all shadow-xs flex items-center space-x-1"
          >
            <span>🔄</span>
            <span>{{ isCompiling ? 'Compilando...' : 'Recompilar' }}</span>
          </button>
          <button
            @click="printReport"
            class="px-3 py-1.5 rounded-sm bg-emerald-600 hover:bg-emerald-500 text-white font-bold transition-all shadow-xs flex items-center space-x-1"
            title="Exportar a PDF o Imprimir Informe"
          >
            <span>🖨️</span>
            <span>Imprimir / PDF</span>
          </button>
          <button
            @click="downloadReportMarkdown"
            class="px-3 py-1.5 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all flex items-center space-x-1"
            title="Descargar archivo REPORT.md"
          >
            <span>💾</span>
            <span>Descargar .md</span>
          </button>
        </div>
      </div>

      <!-- Vista Ejecutiva Imprimible -->
      <div v-if="reportViewMode === 'executive'" class="report-printable space-y-6">
        <!-- Portada / Cabecera Ejecutiva -->
        <div class="tactical-card border-l-4 border-l-cyan-500 space-y-4 print:border-none print:shadow-none print:bg-white print:text-black">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 print:border-slate-300 pb-4">
            <div>
              <div class="text-[10px] font-mono tracking-widest uppercase text-cyan-400 font-bold mb-1 print:text-cyan-700">
                SecLab Tactical Assessment Report
              </div>
              <h1 class="text-xl md:text-2xl font-bold font-mono text-white print:text-black">
                Informe de Auditoría de Seguridad: {{ engId }}
              </h1>
              <p class="text-xs text-slate-400 mt-1 print:text-slate-600">
                Objetivo / Tipo: <span class="text-slate-200 uppercase font-mono print:text-black">{{ engType }}</span> | 
                Metodología: <span class="text-slate-200 font-mono print:text-black">PTES & Scope Guard Evidence-First</span>
              </p>
            </div>
            <div class="text-right text-xs font-mono text-slate-400 print:text-slate-600">
              <div>Fecha de Emisión: <span class="text-slate-200 font-bold print:text-black">{{ reportCompiledDate }}</span></div>
              <div>Auditor Principal: <span class="text-cyan-400 font-bold print:text-black">tester (SecLab Operator)</span></div>
              <div>Estado: <span class="text-emerald-400 font-bold print:text-emerald-700">CONFIRMADO</span></div>
            </div>
          </div>

          <!-- Matriz de Severidades (KPI Badges) -->
          <div class="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-2">
            <div class="bg-purple-950/30 border border-purple-500/40 print:bg-purple-50 print:border-purple-300 rounded-sm p-3 text-center">
              <span class="text-[10px] uppercase font-mono tracking-wider text-purple-400 print:text-purple-800 block font-bold">Crítica</span>
              <span class="text-2xl font-mono font-bold text-purple-300 print:text-purple-900">{{ reportStats.critical }}</span>
            </div>
            <div class="bg-red-950/30 border border-red-500/40 print:bg-red-50 print:border-red-300 rounded-sm p-3 text-center">
              <span class="text-[10px] uppercase font-mono tracking-wider text-red-400 print:text-red-800 block font-bold">Alta</span>
              <span class="text-2xl font-mono font-bold text-red-300 print:text-red-900">{{ reportStats.high }}</span>
            </div>
            <div class="bg-amber-950/30 border border-amber-500/40 print:bg-amber-50 print:border-amber-300 rounded-sm p-3 text-center">
              <span class="text-[10px] uppercase font-mono tracking-wider text-amber-400 print:text-amber-800 block font-bold">Media</span>
              <span class="text-2xl font-mono font-bold text-amber-300 print:text-amber-900">{{ reportStats.medium }}</span>
            </div>
            <div class="bg-blue-950/30 border border-blue-500/40 print:bg-blue-50 print:border-blue-300 rounded-sm p-3 text-center">
              <span class="text-[10px] uppercase font-mono tracking-wider text-blue-400 print:text-blue-800 block font-bold">Baja</span>
              <span class="text-2xl font-mono font-bold text-blue-300 print:text-blue-900">{{ reportStats.low }}</span>
            </div>
            <div class="bg-cyan-950/30 border border-cyan-500/40 print:bg-cyan-50 print:border-cyan-300 rounded-sm p-3 text-center">
              <span class="text-[10px] uppercase font-mono tracking-wider text-cyan-400 print:text-cyan-800 block font-bold">Informativa</span>
              <span class="text-2xl font-mono font-bold text-cyan-300 print:text-cyan-900">{{ reportStats.info }}</span>
            </div>
          </div>
        </div>

        <!-- Cuerpo del Reporte Renderizado -->
        <div class="tactical-card bg-[#050811] p-8 report-content-html overflow-x-auto print:bg-white print:text-black print:border-none print:shadow-none print:p-0">
          <div v-html="renderedReportHtml" class="prose-report"></div>
        </div>
      </div>

      <!-- Vista Markdown Fuente -->
      <div v-else class="space-y-4">
        <div class="tactical-card bg-[#050811] p-6 max-h-[750px] overflow-y-auto font-mono text-xs text-slate-200">
          <pre class="whitespace-pre-wrap selection:bg-cyan-500 selection:text-black">{{ reportContent }}</pre>
        </div>
      </div>
    </div>

    <!-- TAB: BANDERAS CTF & BOTÍN (LOOT / CREDENCIALES) -->
    <div v-if="activeTab === 'flags' || activeTab === 'loot'" class="space-y-6">
      <!-- Sección Banderas CTF (Siempre visible en retos o si hay banderas) -->
      <div class="tactical-card space-y-4 border-l-4" :class="flagsData.subtype === 'jeopardy' ? 'border-l-cyan-500' : 'border-l-amber-500'">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <div class="flex items-center space-x-2">
            <span class="text-xl">🏆</span>
            <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider">
              {{ flagsData.subtype === 'jeopardy' ? 'Bandera CTF Jeopardy & Metadatos' : 'Control de Banderas CTF (Flags)' }}
            </h2>
          </div>
          <button
            @click="saveFlagsAction"
            :disabled="isSavingFlags"
            class="px-3 py-1 rounded-sm text-xs font-mono font-bold transition-colors"
            :class="flagsData.subtype === 'jeopardy' ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950' : 'bg-amber-500 hover:bg-amber-400 text-slate-950'"
          >
            {{ isSavingFlags ? 'Guardando...' : (flagsData.subtype === 'jeopardy' ? 'Guardar Bandera & Writeup' : 'Guardar Banderas') }}
          </button>
        </div>

        <!-- Modo CTF Jeopardy -->
        <div v-if="flagsData.subtype === 'jeopardy'" class="space-y-4">
          <div class="p-4 rounded-lg bg-[#050811] border" :class="flagsData.flag?.status === 'captured' ? 'border-emerald-500/50 shadow-md shadow-emerald-500/10' : 'border-slate-800'">
            <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
              <span class="text-xs font-mono font-bold text-slate-300 flex items-center space-x-1.5">
                <span>🚩</span>
                <span>Bandera Obtenida (Flag)</span>
              </span>
              <button
                @click="toggleFlagStatus('flag')"
                type="button"
                class="px-2.5 py-1 rounded-sm text-[10px] font-mono font-bold uppercase tracking-wider transition-all cursor-pointer"
                :class="flagsData.flag?.status === 'captured' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-xs shadow-emerald-500/20' : 'bg-slate-800 text-slate-400 border border-slate-700 hover:text-slate-200'"
              >
                {{ flagsData.flag?.status === 'captured' ? '✓ CAPTURADA / RESUELTO' : '○ PENDIENTE' }}
              </button>
            </div>
            <input
              v-model="flagsData.flag.value"
              type="text"
              placeholder="flag{...}, CTF{...}, picoCTF{...}"
              class="w-full bg-[#0b101d] border border-slate-800 focus:border-cyan-400 rounded-sm px-3 py-2 text-xs font-mono text-emerald-400 placeholder-slate-600 focus:outline-hidden"
            />
            <div v-if="flagsData.flag?.captured_at" class="text-[10px] font-mono text-slate-500 mt-1">
              Capturada: {{ flagsData.flag.captured_at }}
            </div>
          </div>

          <!-- Metadatos de la categoría, dificultad y puntuación -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4 rounded-lg bg-[#050811] border border-slate-800">
            <div>
              <label class="block text-[11px] font-mono text-slate-400 mb-1">Categoría Técnica:</label>
              <select
                v-model="flagsData.category"
                class="w-full bg-[#0b101d] border border-slate-700 focus:border-cyan-400 rounded-sm px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-hidden"
              >
                <option value="web">🌐 Web Exploitation</option>
                <option value="crypto">🔐 Criptografía</option>
                <option value="pwn">💥 Binary Exploitation (Pwn)</option>
                <option value="reverse">⚙️ Reverse Engineering</option>
                <option value="forensics">🔍 Forensics</option>
                <option value="osint">🛰️ OSINT</option>
                <option value="misc">📦 Misc</option>
              </select>
            </div>
            <div>
              <label class="block text-[11px] font-mono text-slate-400 mb-1">Dificultad:</label>
              <select
                v-model="flagsData.difficulty"
                class="w-full bg-[#0b101d] border border-slate-700 focus:border-cyan-400 rounded-sm px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-hidden"
              >
                <option value="easy">Fácil</option>
                <option value="medium">Media</option>
                <option value="hard">Difícil</option>
                <option value="insane">Insane</option>
              </select>
            </div>
            <div>
              <label class="block text-[11px] font-mono text-slate-400 mb-1">Puntos:</label>
              <input
                v-model.number="flagsData.points"
                type="number"
                min="0"
                step="10"
                class="w-full bg-[#0b101d] border border-slate-700 focus:border-cyan-400 rounded-sm px-2.5 py-1.5 text-xs font-mono text-slate-200 focus:outline-hidden"
              />
            </div>
          </div>

          <!-- Notas tácticas / Writeup del reto -->
          <div class="p-4 rounded-lg bg-[#050811] border border-slate-800 space-y-2">
            <div class="flex items-center justify-between">
              <label class="text-xs font-mono font-bold text-slate-300 flex items-center space-x-1.5">
                <span>📝</span>
                <span>Notas Tácticas & Procedimiento de Solución (Writeup)</span>
              </label>
              <span class="text-[10px] font-mono text-slate-500">Persiste en flags.json</span>
            </div>
            <textarea
              v-model="flagsData.flag.notes"
              rows="4"
              placeholder="Documenta el payload, script en python utilizado, vulnerabilidad explotada o comando que reveló la flag..."
              class="w-full bg-[#0b101d] border border-slate-800 focus:border-cyan-400 rounded-sm p-3 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-hidden"
            ></textarea>
          </div>
        </div>

        <!-- Modo CTF Máquina Tradicional (User / Root) -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- User Flag -->
          <div class="p-4 rounded-lg bg-[#050811] border" :class="flagsData.user_flag?.status === 'captured' ? 'border-emerald-500/50 shadow-md shadow-emerald-500/10' : 'border-slate-800'">
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-mono font-bold text-slate-300 flex items-center space-x-1.5">
                <span>👤</span>
                <span>User Flag / Shell Inicial</span>
              </span>
              <button
                @click="toggleFlagStatus('user_flag')"
                class="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold uppercase tracking-wider transition-all"
                :class="flagsData.user_flag?.status === 'captured' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-slate-800 text-slate-400 border border-slate-700'"
              >
                {{ flagsData.user_flag?.status === 'captured' ? '✓ CAPTURADA' : '○ PENDIENTE' }}
              </button>
            </div>
            <input
              v-model="flagsData.user_flag.value"
              type="text"
              placeholder="THM{...}, HTB{...}, flag{...}"
              class="w-full bg-[#0b101d] border border-slate-800 focus:border-amber-400 rounded-sm px-3 py-2 text-xs font-mono text-emerald-400 placeholder-slate-600 focus:outline-hidden"
            />
            <div v-if="flagsData.user_flag?.captured_at" class="text-[10px] font-mono text-slate-500 mt-1">
              Capturada: {{ flagsData.user_flag.captured_at }}
            </div>
          </div>

          <!-- Root Flag -->
          <div class="p-4 rounded-lg bg-[#050811] border" :class="flagsData.root_flag?.status === 'captured' ? 'border-purple-500/50 shadow-md shadow-purple-500/10' : 'border-slate-800'">
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-mono font-bold text-slate-300 flex items-center space-x-1.5">
                <span>⚡</span>
                <span>Root Flag / Escalación de Privilegios</span>
              </span>
              <button
                @click="toggleFlagStatus('root_flag')"
                class="px-2 py-0.5 rounded-sm text-[10px] font-mono font-bold uppercase tracking-wider transition-all"
                :class="flagsData.root_flag?.status === 'captured' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40' : 'bg-slate-800 text-slate-400 border border-slate-700'"
              >
                {{ flagsData.root_flag?.status === 'captured' ? '✓ ROOT CAPTURADO' : '○ PENDIENTE' }}
              </button>
            </div>
            <input
              v-model="flagsData.root_flag.value"
              type="text"
              placeholder="root{...}, HTB{root_...}"
              class="w-full bg-[#0b101d] border border-slate-800 focus:border-purple-400 rounded-sm px-3 py-2 text-xs font-mono text-purple-300 placeholder-slate-600 focus:outline-hidden"
            />
            <div v-if="flagsData.root_flag?.captured_at" class="text-[10px] font-mono text-slate-500 mt-1">
              Capturada: {{ flagsData.root_flag.captured_at }}
            </div>
          </div>
        </div>
      </div>

      <!-- Tabla de Botín y Credenciales (Loot) -->
      <div class="tactical-card space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div>
            <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider flex items-center space-x-2">
              <span>🔑 Botín de Credenciales & Acceso (loot/credentials.json)</span>
            </h2>
            <p class="text-xs text-slate-400">Contraseñas comprometidas, hashes recuperados y cuentas de servicio.</p>
          </div>
          <button
            @click="showCredModal = true"
            class="px-3 py-1.5 rounded-sm bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold text-xs font-mono flex items-center space-x-1"
          >
            <span>+</span>
            <span>Registrar Credencial</span>
          </button>
        </div>

        <div v-if="lootData.credentials.length === 0" class="text-center py-8 text-slate-500 font-mono text-xs">
          No hay credenciales registradas aún en el botín. Haz clic en "Registrar Credencial".
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-left font-mono text-xs border-collapse">
            <thead>
              <tr class="border-b border-slate-800 text-slate-400 text-[11px] bg-slate-900/60">
                <th class="p-2.5">SERVICIO</th>
                <th class="p-2.5">HOST / PUERTO</th>
                <th class="p-2.5">USUARIO</th>
                <th class="p-2.5">CONTRASEÑA / HASH</th>
                <th class="p-2.5">ROL / NOTAS</th>
                <th class="p-2.5 text-right">ACCIONES</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60">
              <tr v-for="c in lootData.credentials" :key="c.id" class="hover:bg-slate-900/40">
                <td class="p-2.5">
                  <span class="px-1.5 py-0.5 rounded-sm text-[10px] uppercase font-bold bg-cyan-950/80 text-cyan-300 border border-cyan-500/30">
                    {{ c.service || 'HTTP' }}
                  </span>
                </td>
                <td class="p-2.5 text-slate-300">{{ c.host || '-' }}<span v-if="c.port">:{{ c.port }}</span></td>
                <td class="p-2.5 text-white font-bold">{{ c.username || '-' }}</td>
                <td class="p-2.5">
                  <div class="flex items-center space-x-1">
                    <code class="bg-[#050811] px-2 py-0.5 rounded-sm text-amber-300 border border-slate-800">{{ c.password || c.hash || '-' }}</code>
                    <button @click="copyText(c.password || c.hash)" class="text-slate-500 hover:text-cyan-400 text-[10px]">📋</button>
                  </div>
                </td>
                <td class="p-2.5 text-slate-400 text-[11px]">{{ c.notes || c.role || '-' }}</td>
                <td class="p-2.5 text-right">
                  <button @click="deleteCredAction(c.id)" class="text-red-400 hover:text-red-300 text-xs font-bold">&times;</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Archivos de Botín en disco (loot/*) -->
      <div v-if="lootData.files && lootData.files.length > 0" class="tactical-card space-y-3">
        <h3 class="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
          <span>📦 Archivos de Volcado en /loot</span>
        </h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 font-mono text-xs">
          <div v-for="f in lootData.files" :key="f.name" class="p-2.5 bg-[#050811] rounded-sm border border-slate-800 flex items-center justify-between">
            <span class="text-slate-300 truncate">{{ f.name }}</span>
            <span class="text-[10px] text-slate-500">{{ (f.size / 1024).toFixed(1) }} KB</span>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB: EXPLORADOR DE ARTEFACTOS & ARCHIVOS -->
    <div v-if="activeTab === 'artifacts'" class="space-y-4">
      <div class="tactical-card space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
          <div class="flex items-center space-x-2">
            <span class="text-lg">📁</span>
            <h2 class="text-sm font-mono font-bold text-white uppercase tracking-wider">
              Artefactos del Laboratorio
            </h2>
          </div>

          <!-- Selector de Subcarpeta -->
          <div class="flex items-center space-x-1 text-xs font-mono overflow-x-auto">
            <button
              v-for="folder in ['recon', 'fuzzing', 'loot', 'screenshots', 'exports', 'evidence']"
              :key="folder"
              @click="selectArtifactFolder(folder)"
              class="px-2.5 py-1 rounded-sm transition-colors uppercase tracking-wider text-[11px]"
              :class="activeArtifactFolder === folder ? 'bg-cyan-500 text-slate-950 font-bold' : 'bg-slate-800 text-slate-400 hover:text-white'"
            >
              {{ folder }}/
            </button>
          </div>
        </div>

        <!-- Lista de Archivos y Previsualizador -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <!-- Columna Archivos -->
          <div class="bg-[#050811] border border-slate-800 rounded-sm p-2 max-h-[500px] overflow-y-auto space-y-1 font-mono text-xs">
            <div v-if="artifactFiles.length === 0" class="text-center py-10 text-slate-600">
              No hay archivos generados en {{ activeArtifactFolder }}/
            </div>
            <button
              v-for="file in artifactFiles"
              :key="file.rel_path"
              @click="loadArtifactPreview(file)"
              class="w-full text-left p-2 rounded-sm flex items-center justify-between transition-colors"
              :class="selectedArtifact?.rel_path === file.rel_path ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-500/40' : 'hover:bg-slate-900 text-slate-300'"
            >
              <span class="truncate">{{ file.name }}</span>
              <span class="text-[10px] text-slate-500 ml-2 whitespace-nowrap">{{ (file.size / 1024).toFixed(1) }} KB</span>
            </button>
          </div>

          <!-- Columna Previsualizador -->
          <div class="lg:col-span-2 bg-[#050811] border border-slate-800 rounded-sm p-4 max-h-[500px] overflow-y-auto font-mono text-xs">
            <div v-if="!selectedArtifact" class="text-center py-20 text-slate-600">
              Selecciona un archivo de la lista para previsualizar su contenido.
            </div>
            <div v-else class="space-y-3">
              <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                <span class="text-cyan-400 font-bold">{{ selectedArtifact.rel_path }}</span>
                <button
                  @click="copyText(selectedArtifactContent)"
                  class="px-2 py-1 rounded-sm bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px]"
                >
                  Copiar Contenido
                </button>
              </div>
              <pre class="whitespace-pre-wrap text-slate-200 text-xs overflow-x-auto">{{ selectedArtifactContent }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- MODAL REGISTRAR CREDENCIAL DE BOTÍN -->
    <div
      v-if="showCredModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 overflow-y-auto"
    >
      <div class="bg-[#0d1322] border border-cyan-500/40 rounded-lg max-w-md w-full p-6 shadow-2xl space-y-4">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 class="text-sm font-mono font-bold text-white flex items-center space-x-2">
            <span>🔑 Registrar Credencial en Botín</span>
          </h2>
          <button @click="showCredModal = false" class="text-slate-400 hover:text-white font-mono text-lg">&times;</button>
        </div>

        <form @submit.prevent="submitCredential" class="space-y-3 text-xs font-mono">
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="text-slate-400 block mb-1">Servicio:</label>
              <select v-model="credForm.service" class="w-full bg-[#070b14] border border-slate-700 rounded-sm p-1.5 text-slate-200">
                <option value="SSH">SSH (:22)</option>
                <option value="HTTP">HTTP/Web</option>
                <option value="SMB">SMB (:445)</option>
                <option value="FTP">FTP (:21)</option>
                <option value="MySQL">MySQL (:3306)</option>
                <option value="Postgres">PostgreSQL (:5432)</option>
                <option value="RDP">RDP (:3389)</option>
                <option value="WinRM">WinRM (:5985)</option>
                <option value="Other">Otro</option>
              </select>
            </div>
            <div>
              <label class="text-slate-400 block mb-1">Host / Destino:</label>
              <input
                v-model="credForm.host"
                type="text"
                placeholder="10.10.10.42"
                class="w-full bg-[#070b14] border border-slate-700 rounded-sm px-2.5 py-1.5 text-slate-100"
              />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="text-slate-400 block mb-1">Usuario:</label>
              <input
                v-model="credForm.username"
                type="text"
                placeholder="admin, root, user"
                class="w-full bg-[#070b14] border border-slate-700 rounded-sm px-2.5 py-1.5 text-slate-100"
              />
            </div>
            <div>
              <label class="text-slate-400 block mb-1">Puerto (opcional):</label>
              <input
                v-model="credForm.port"
                type="number"
                placeholder="22"
                class="w-full bg-[#070b14] border border-slate-700 rounded-sm px-2.5 py-1.5 text-slate-100"
              />
            </div>
          </div>

          <div>
            <label class="text-slate-400 block mb-1">Contraseña o Hash:</label>
            <input
              v-model="credForm.password"
              type="text"
              required
              placeholder="P@ssw0rd123! o $6$hash..."
              class="w-full bg-[#070b14] border border-slate-700 rounded-sm px-2.5 py-1.5 text-amber-300 font-bold"
            />
          </div>

          <div>
            <label class="text-slate-400 block mb-1">Notas / Origen del Hallazgo:</label>
            <input
              v-model="credForm.notes"
              type="text"
              placeholder="Encontrado en config.php o crackeado con john"
              class="w-full bg-[#070b14] border border-slate-700 rounded-sm px-2.5 py-1.5 text-slate-300"
            />
          </div>

          <div class="flex justify-end space-x-2 pt-3 border-t border-slate-800">
            <button
              type="button"
              @click="showCredModal = false"
              class="px-3 py-1.5 rounded-sm bg-slate-800 text-slate-400 hover:text-white"
            >
              Cancelar
            </button>
            <button
              type="submit"
              class="px-4 py-1.5 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold"
            >
              Guardar Credencial
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- MODAL CREAR / EDITAR HALLAZGO CON CVSS CALCULATOR -->
    <div
      v-if="showFindingModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 overflow-y-auto"
    >
      <div class="bg-[#0d1322] border border-cyan-500/40 rounded-lg max-w-2xl w-full p-6 shadow-2xl space-y-4 my-8 max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 class="text-base font-mono font-bold text-white flex items-center space-x-2">
            <span>🛡️ Ficha de Hallazgo (Evidence-First)</span>
          </h2>
          <button @click="showFindingModal = false" class="text-slate-400 hover:text-white font-mono text-lg">&times;</button>
        </div>

        <form @submit.prevent="submitFinding" class="space-y-4">
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">Slug / Identificador:</label>
              <input
                v-model="findingForm.slug"
                type="text"
                required
                placeholder="idor-user-profile, sqli-login"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
              />
            </div>
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">Estado de Evidencia:</label>
              <select
                v-model="findingForm.status"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
              >
                <option value="PROVEN">PROVEN (Demostrado / Control Negativo)</option>
                <option value="CANDIDATE">CANDIDATE (Hipótesis por confirmar)</option>
                <option value="DISPROVED">DISPROVED (Falso positivo refutado)</option>
                <option value="MITIGATED">MITIGATED (Mitigado)</option>
                <option value="DRAFT">DRAFT (Borrador)</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">Activo Afectado:</label>
              <input
                v-model="findingForm.asset"
                type="text"
                placeholder="api.target.local/v1/profile"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
              />
            </div>
          </div>

          <div>
            <label class="block text-xs font-mono text-slate-300 mb-1">Título de la Vulnerabilidad:</label>
            <input
              v-model="findingForm.title"
              type="text"
              required
              placeholder="Insecure Direct Object Reference (IDOR) en Actualización de Cuenta"
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
            />
          </div>

          <!-- Calculadora CVSS 3.1 Interactiva -->
          <div class="p-3 rounded-sm bg-slate-900/80 border border-slate-800 space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider">Calculadora CVSS 3.1</span>
              <span class="text-xs font-mono font-bold" :class="getSeverityClass(findingForm.severity)">
                {{ findingForm.severity }} (Score: {{ findingForm.cvss_score || '5.0' }})
              </span>
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
              <div>
                <label class="text-slate-400 block mb-0.5">Attack Vector (AV):</label>
                <select v-model="cvssMetrics.AV" @change="recalcCvss" class="w-full bg-[#070b14] border border-slate-700 rounded-sm p-1 text-slate-200">
                  <option value="N">Network (N)</option>
                  <option value="A">Adjacent (A)</option>
                  <option value="L">Local (L)</option>
                  <option value="P">Physical (P)</option>
                </select>
              </div>
              <div>
                <label class="text-slate-400 block mb-0.5">Attack Complexity (AC):</label>
                <select v-model="cvssMetrics.AC" @change="recalcCvss" class="w-full bg-[#070b14] border border-slate-700 rounded-sm p-1 text-slate-200">
                  <option value="L">Low (L)</option>
                  <option value="H">High (H)</option>
                </select>
              </div>
              <div>
                <label class="text-slate-400 block mb-0.5">Privileges Req (PR):</label>
                <select v-model="cvssMetrics.PR" @change="recalcCvss" class="w-full bg-[#070b14] border border-slate-700 rounded-sm p-1 text-slate-200">
                  <option value="N">None (N)</option>
                  <option value="L">Low (L)</option>
                  <option value="H">High (H)</option>
                </select>
              </div>
              <div>
                <label class="text-slate-400 block mb-0.5">User Interaction (UI):</label>
                <select v-model="cvssMetrics.UI" @change="recalcCvss" class="w-full bg-[#070b14] border border-slate-700 rounded-sm p-1 text-slate-200">
                  <option value="N">None (N)</option>
                  <option value="R">Required (R)</option>
                </select>
              </div>
            </div>
            <div class="text-[10px] font-mono text-slate-500">{{ findingForm.cvss_vector }}</div>
          </div>

          <div>
            <label class="block text-xs font-mono text-slate-300 mb-1">Descripción del Hallazgo:</label>
            <textarea
              v-model="findingForm.description"
              rows="3"
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
              placeholder="Explicación detallada del fallo y cómo fue detectado..."
            ></textarea>
          </div>

          <div>
            <label class="block text-xs font-mono text-slate-300 mb-1">Pasos para Reproducir (PoC):</label>
            <textarea
              v-model="findingForm.steps_to_reproduce"
              rows="3"
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
              placeholder="1. Realizar petición POST con token de usuario A&#10;2. Modificar id a usuario B..."
            ></textarea>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">Evidencia HTTP (Petición):</label>
              <textarea
                v-model="findingForm.http_request"
                rows="4"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
                placeholder="GET /api/user/102 HTTP/1.1&#10;Host: target.local..."
              ></textarea>
            </div>
            <div>
              <label class="block text-xs font-mono text-slate-300 mb-1">Evidencia HTTP (Respuesta):</label>
              <textarea
                v-model="findingForm.http_response"
                rows="4"
                class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
                placeholder="HTTP/1.1 200 OK&#10;Content-Type: application/json..."
              ></textarea>
            </div>
          </div>

          <div>
            <label class="block text-xs font-mono text-slate-300 mb-1">Remediación y Mitigación Sugerida:</label>
            <input
              v-model="findingForm.remediation"
              type="text"
              placeholder="Implementar validación de control de acceso a nivel de objeto (BOLA/IDOR)..."
              class="w-full bg-[#070b14] border border-slate-700 focus:border-cyan-400 rounded-sm px-3 py-1.5 text-xs font-mono text-slate-100 focus:outline-hidden"
            />
          </div>

          <div class="pt-3 border-t border-slate-800 flex items-center justify-end space-x-3">
            <button
              type="button"
              @click="showFindingModal = false"
              class="px-4 py-2 rounded-sm bg-slate-800 text-slate-300 text-xs font-mono"
            >
              Cancelar
            </button>
            <button
              type="submit"
              class="px-5 py-2 rounded-sm bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs font-mono"
            >
              Guardar Ficha
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { renderReport } from '../report-security'
import { splitIpsAndCidrs } from '../scope-utils'
import { api } from '../api'
import DeleteProjectButton from '../components/DeleteProjectButton.vue'

const route = useRoute()
const router = useRouter()
const engId = computed(() => route.params.id)
const engType = computed(() => route.params.type || 'engagement')

const activeTab = ref(engType.value === 'reto' ? 'flags' : 'scope')

// Banderas CTF & Botín (Loot)
const flagsData = ref({
  subtype: 'machine',
  category: 'misc',
  points: 100,
  difficulty: 'medium',
  flag: { value: '', status: 'pending', captured_at: null, notes: '' },
  user_flag: { value: '', status: 'pending', captured_at: null },
  root_flag: { value: '', status: 'pending', captured_at: null },
  custom_flags: [],
})
const isSavingFlags = ref(false)

const isProjectSolved = computed(() => {
  if (flagsData.value.subtype === 'jeopardy') {
    return flagsData.value.flag?.status === 'captured'
  }
  return flagsData.value.root_flag?.status === 'captured'
})

const lootData = ref({ credentials: [], files: [] })
const showCredModal = ref(false)
const credForm = ref({
  service: 'SSH',
  host: '',
  port: 22,
  username: '',
  password: '',
  notes: '',
})

// Reconocimiento & Scope Guard Pipeline
const reconStatus = ref({
  job: { status: 'idle' },
  summary: {
    subdomains_count: 0,
    subdomains_discarded_out_of_scope: 0,
    live_hosts_count: 0,
    urls_count: 0,
    js_files_count: 0,
    gf_patterns: {},
  },
  configured_domains: [],
  discarded_out_of_scope: [],
})
const reconStage = ref('all')
const reconDryRun = ref(false)
const reconLogContent = ref('')
const isStartingRecon = ref(false)
const isCancellingRecon = ref(false)
const reconActionMsg = ref('')
const reconActionSuccess = ref(true)
let reconPollTimer = null

const reconIsRunning = computed(() => ['running', 'cancelling'].includes(reconStatus.value.job?.status))
const reconJobLabel = computed(() => ({ running: '● EJECUTANDO', cancelling: 'CANCELANDO', completed: 'COMPLETADO', failed: 'FALLIDO', simulated: 'SIMULADO', interrupted: 'INTERRUMPIDO', cancelled: 'CANCELADO' })[reconStatus.value.job?.status] || 'LISTO')

// Artefactos del laboratorio (recon/, fuzzing/, loot/, etc.)
const activeArtifactFolder = ref('recon')
const artifactFiles = ref([])
const selectedArtifact = ref(null)
const selectedArtifactContent = ref('')

const capturedFlagsCount = computed(() => {
  if (flagsData.value.subtype === 'jeopardy') {
    return flagsData.value.flag?.status === 'captured' ? 1 : 0
  }
  let count = 0
  if (flagsData.value.user_flag?.status === 'captured') count++
  if (flagsData.value.root_flag?.status === 'captured') count++
  return count
})

const tabs = computed(() => {
  if (engType.value === 'reto') {
    return [
      { id: 'flags', label: '🚩 Banderas & Loot', icon: '🏆', count: capturedFlagsCount.value },
      { id: 'scope', label: 'Objetivo & Scope', icon: '🎯' },
      { id: 'recon', label: 'Reconocimiento', icon: '📡', count: reconStatus.value.summary?.subdomains_count },
      { id: 'findings', label: 'Vectores / Hallazgos', icon: '📋', count: findings.value.length },
      { id: 'artifacts', label: 'Artefactos & Dumps', icon: '📁', count: artifactFiles.value.length },
      { id: 'logs', label: 'Terminal Logs', icon: '⚡' },
      { id: 'copilot', label: 'Copiloto CTF', icon: '🤖' },
      { id: 'notes', label: 'Solución (notes.md)', icon: '📝' },
      { id: 'report', label: 'Writeup (REPORT.md)', icon: '📄' },
    ]
  }
  return [
    { id: 'scope', label: 'Alcance (target.yaml)', icon: '🎯' },
    { id: 'recon', label: 'Reconocimiento', icon: '📡', count: reconStatus.value.summary?.subdomains_count },
    { id: 'findings', label: 'Hallazgos (evidence/)', icon: '📋', count: findings.value.length },
    { id: 'loot', label: 'Botín & Credenciales', icon: '🔑', count: lootData.value.credentials.length },
    { id: 'artifacts', label: 'Artefactos (recon/)', icon: '📁', count: artifactFiles.value.length },
    { id: 'logs', label: 'Terminal Logs', icon: '⚡' },
    { id: 'checklist', label: 'Metodología & Cobertura', icon: '📊' },
    { id: 'copilot', label: 'Copiloto Táctico', icon: '🤖' },
    { id: 'notes', label: 'Notas (notes.md)', icon: '📝' },
    { id: 'report', label: 'Reporte (REPORT.md)', icon: '📄' },
  ]
})

// Scope
const scopeData = ref({})
const inScopeDomainsText = ref('')
const inScopeIpsText = ref('')
const outScopeDomainsText = ref('')
const outScopeNotesText = ref('')
const hasScope = ref(false)
const isSavingScope = ref(false)

const scopeTestInput = ref('')
const scopeTestResult = ref(null)

// Findings
const findings = ref([])
const showFindingModal = ref(false)
const findingForm = ref({
  slug: '',
  title: '',
  status: 'PROVEN',
  severity: 'MEDIUM',
  cvss_score: 5.3,
  cvss_vector: 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N',
  cwe: 'CWE-200',
  asset: '',
  description: '',
  steps_to_reproduce: '',
  http_request: '',
  http_response: '',
  remediation: '',
})

const cvssMetrics = ref({
  AV: 'N', AC: 'L', PR: 'N', UI: 'N', S: 'U', C: 'L', I: 'N', A: 'N'
})

// Logs
const logContent = ref('')

// Checklist & Next
const checklistData = ref({})
const nextStepData = ref({})
const agentPrompt = ref('')

// Notes
const notesContent = ref('')
const isSavingNotes = ref(false)

// Report & Pack
const reportContent = ref('')
const isCompiling = ref(false)
const isPacking = ref(false)
const reportViewMode = ref('executive')

const reportStats = computed(() => {
  const stats = { critical: 0, high: 0, medium: 0, low: 0, info: 0 }
  if (findings.value && findings.value.length > 0) {
    for (const f of findings.value) {
      const sev = (f.severity || f.frontmatter?.severity || '').toUpperCase()
      if (sev === 'CRITICAL') stats.critical++
      else if (sev === 'HIGH') stats.high++
      else if (sev === 'MEDIUM') stats.medium++
      else if (sev === 'LOW') stats.low++
      else stats.info++
    }
    return stats
  }
  if (reportContent.value) {
    const crit = reportContent.value.match(/Crítica:\*\*\s*(\d+)/i)
    const high = reportContent.value.match(/Alta:\*\*\s*(\d+)/i)
    const med = reportContent.value.match(/Media:\*\*\s*(\d+)/i)
    const low = reportContent.value.match(/Baja:\*\*\s*(\d+)/i)
    const inf = reportContent.value.match(/Informativa:\*\*\s*(\d+)/i)
    if (crit) stats.critical = parseInt(crit[1], 10)
    if (high) stats.high = parseInt(high[1], 10)
    if (med) stats.medium = parseInt(med[1], 10)
    if (low) stats.low = parseInt(low[1], 10)
    if (inf) stats.info = parseInt(inf[1], 10)
  }
  return stats
})

const reportCompiledDate = computed(() => {
  if (reportContent.value) {
    const match = reportContent.value.match(/Fecha:\*\*\s*([^\n]+)/i)
    if (match) return match[1].trim()
  }
  return new Date().toISOString().split('T')[0]
})

const renderedReportHtml = computed(() => {
  if (!reportContent.value) return '<p class="text-slate-500 font-mono">No hay informe compilado aún. Haz clic en "Compilar Reporte".</p>'
  try {
    return renderReport(reportContent.value)
  } catch (err) {
    return '<p class="text-red-400 font-mono">No se pudo mostrar el informe.</p>'
  }
})

async function loadReport() {
  try {
    const res = await api.previewReport(engId.value, engType.value)
    if (res.content) {
      reportContent.value = res.content
    }
  } catch (err) {
    console.error('Error al cargar reporte:', err)
  }
}

function printReport() {
  window.print()
}

function downloadReportMarkdown() {
  const blob = new Blob([reportContent.value || ''], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `REPORT-${engId.value}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function getSeverityClass(sev) {
  switch (String(sev).toUpperCase()) {
    case 'CRITICAL': return 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
    case 'HIGH': return 'bg-red-500/20 text-red-300 border border-red-500/40'
    case 'MEDIUM': return 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
    case 'LOW': return 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
    default: return 'bg-slate-700 text-slate-300'
  }
}

function getFindingStatusClass(status) {
  switch (String(status || '').toUpperCase()) {
    case 'PROVEN':
    case 'VERIFIED':
    case 'CONFIRMADO':
      return 'bg-emerald-950/80 text-emerald-300 border-emerald-500/50'
    case 'CANDIDATE':
      return 'bg-amber-950/80 text-amber-300 border-amber-500/50'
    case 'DISPROVED':
    case 'FALSO_POSITIVO':
      return 'bg-purple-950/80 text-purple-300 border-purple-500/50'
    case 'MITIGATED':
    case 'MITIGADO':
      return 'bg-cyan-950/80 text-cyan-300 border-cyan-500/50'
    case 'DRAFT':
    case 'BORRADOR':
      return 'bg-slate-800 text-slate-300 border-slate-700'
    default:
      return 'bg-slate-800 text-slate-300 border-slate-700'
  }
}

async function loadScope() {
  try {
    const data = await api.getScope(engId.value, engType.value)
    scopeData.value = data
    hasScope.value = !!data.scope
    const inScope = data.scope?.in_scope || {}
    const outScope = data.scope?.out_of_scope || {}
    inScopeDomainsText.value = (inScope.domains || []).join('\n')
    inScopeIpsText.value = [...(inScope.ips || []), ...(inScope.cidrs || [])].join('\n')
    outScopeDomainsText.value = (outScope.domains || []).join('\n')
    outScopeNotesText.value = (outScope.notes || []).join('\n')
  } catch (err) {
    console.error('Error al cargar alcance:', err)
  }
}

async function saveScopeConfig() {
  isSavingScope.value = true
  try {
    const { ips: inScopeIps, cidrs: inScopeCidrs } = splitIpsAndCidrs(inScopeIpsText.value)
    // No hay campo en el formulario para endpoints ni para IPs/CIDRs excluidos:
    // se conservan los valores ya cargados en vez de pisarlos con [].
    const existingInScope = scopeData.value.scope?.in_scope || {}
    const existingOutScope = scopeData.value.scope?.out_of_scope || {}
    const payload = {
      ...scopeData.value,
      scope: {
        in_scope: {
          domains: inScopeDomainsText.value.split('\n').map(s => s.trim()).filter(Boolean),
          ips: inScopeIps,
          cidrs: inScopeCidrs,
          endpoints: existingInScope.endpoints || [],
        },
        out_of_scope: {
          domains: outScopeDomainsText.value.split('\n').map(s => s.trim()).filter(Boolean),
          ips: existingOutScope.ips || [],
          cidrs: existingOutScope.cidrs || [],
          notes: outScopeNotesText.value.split('\n').map(s => s.trim()).filter(Boolean),
        }
      }
    }
    await api.updateScope(engId.value, payload, engType.value)
    await loadScope()
  } catch (err) {
    alert('Error al guardar alcance: ' + err.message)
  } finally {
    isSavingScope.value = false
  }
}

async function testScope() {
  if (!scopeTestInput.value.trim()) return
  try {
    scopeTestResult.value = await api.checkScope(scopeTestInput.value.trim(), engId.value, engType.value)
  } catch (err) {
    scopeTestResult.value = { allowed: false, status: 'ERROR', reason: err.message }
  }
}

async function loadFindings() {
  try {
    findings.value = await api.getFindings(engId.value, engType.value)
    const findingsTab = tabs.value.find(t => t.id === 'findings')
    if (findingsTab) findingsTab.count = findings.value.length
  } catch (err) {
    console.error('Error al cargar hallazgos:', err)
  }
}

function openNewFindingModal() {
  findingForm.value = {
    slug: '',
    title: '',
    status: 'PROVEN',
    severity: 'MEDIUM',
    cvss_score: 5.3,
    cvss_vector: 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N',
    cwe: 'CWE-200',
    asset: '',
    description: '',
    steps_to_reproduce: '',
    http_request: '',
    http_response: '',
    remediation: '',
  }
  showFindingModal.value = true
}

function editFinding(f) {
  findingForm.value = {
    slug: f.slug,
    title: f.frontmatter?.title || '',
    status: f.frontmatter?.status || 'PROVEN',
    severity: f.frontmatter?.severity || 'MEDIUM',
    cvss_score: f.frontmatter?.cvss_score || 5.0,
    cvss_vector: f.frontmatter?.cvss_vector || '',
    cwe: f.frontmatter?.cwe || '',
    asset: f.frontmatter?.asset || '',
    description: f.body || '',
    steps_to_reproduce: '',
    http_request: '',
    http_response: '',
    remediation: '',
  }
  showFindingModal.value = true
}

async function recalcCvss() {
  try {
    const res = await api.calculateCvss(cvssMetrics.value)
    findingForm.value.cvss_score = res.score
    findingForm.value.severity = res.severity
    findingForm.value.cvss_vector = res.vector
  } catch (err) {
    console.error('Error CVSS:', err)
  }
}

async function submitFinding() {
  try {
    await api.saveFinding(engId.value, findingForm.value, engType.value)
    showFindingModal.value = false
    await loadFindings()
  } catch (err) {
    alert('Error al guardar hallazgo: ' + err.message)
  }
}

async function deleteFindingAction(slug) {
  if (!confirm(`¿Eliminar la ficha de evidencia ${slug}?`)) return
  try {
    await api.deleteFinding(engId.value, slug, engType.value)
    await loadFindings()
  } catch (err) {
    alert(err.message)
  }
}

async function loadLogs() {
  try {
    const res = await api.getLogs(engId.value, 500, engType.value)
    logContent.value = res.content
  } catch (err) {
    logContent.value = 'Error al cargar logs: ' + err.message
  }
}

async function loadChecklist() {
  try {
    checklistData.value = await api.getChecklist(engId.value, engType.value)
    nextStepData.value = await api.getNextStep(engId.value, false, engType.value)
  } catch (err) {
    console.error('Error al cargar checklist:', err)
  }
}

async function loadNextStepPrompt() {
  try {
    const res = await api.getNextStep(engId.value, true, engType.value)
    agentPrompt.value = res.prompt || res.raw || JSON.stringify(res, null, 2)
  } catch (err) {
    agentPrompt.value = err.message
  }
}

async function loadNotes() {
  try {
    const detail = await api.getEngagementDetail(engId.value, engType.value)
    notesContent.value = detail.notes || ''
  } catch (err) {
    console.error('Error al cargar notas:', err)
  }
}

async function saveNotes() {
  isSavingNotes.value = true
  try {
    await api.updateNotes(engId.value, notesContent.value, engType.value)
  } catch (err) {
    alert(err.message)
  } finally {
    isSavingNotes.value = false
  }
}

async function compileReportAction() {
  isCompiling.value = true
  try {
    const res = await api.compileReport(engId.value, engType.value)
    reportContent.value = res.content || res.log
    activeTab.value = 'report'
    await loadReport()
  } catch (err) {
    alert('Error al compilar reporte: ' + err.message)
  } finally {
    isCompiling.value = false
  }
}

async function packEngagementAction() {
  isPacking.value = true
  try {
    const res = await api.packReport(engId.value, engType.value)
    // Disparar descarga del paquete al navegador del operador
    const downloadUrl = api.getDownloadReportUrl(engId.value, engType.value)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.setAttribute('download', res.latest_bundle || `${engId.value}_bundle.tar.gz`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (err) {
    alert('Error al empaquetar: ' + err.message)
  } finally {
    isPacking.value = false
  }
}

// ==============================================================================
// Copiloto Táctico IA (Inyección de Contexto en Tiempo Real)
// ==============================================================================
const selectedAgent = ref('triage-agent')
const copilotProfile = ref('quick')
const copilotSelectedModel = ref('profile:quick')
const copilotModels = ref([])
const copilotModelsError = ref('')
const copilotMessages = ref([])
const copilotInput = ref('')
const isCopilotThinking = ref(false)
const showContextModal = ref(false)
const injectedContextText = ref('')

async function loadCopilotModels() {
  try {
    const keys = await api.getVaultKeys()
    const key = keys.find(k => k.provider === 'openrouter' && k.is_active) || keys.find(k => {
      try { return k.provider === 'custom_llm' && k.is_active && ['openrouter.ai', 'eu.openrouter.ai'].includes(new URL(k.base_url.trim().includes('://') ? k.base_url.trim() : `https://${k.base_url.trim()}`).hostname) } catch { return false }
    })
    if (!key) return
    const catalog = await api.getProviderModels(key.provider)
    copilotModels.value = catalog.models
    if (catalog.models.some(m => m.id === catalog.default_model) && !localStorage.getItem(`seclab_copilot_model_${engId.value}`) && !localStorage.getItem('seclab_default_audit_model')) {
      copilotSelectedModel.value = `openrouter:${catalog.default_model}`
    }
  } catch (err) { copilotModelsError.value = err.message }
}

function initCopilotModel() {
  if (typeof localStorage !== 'undefined') {
    const engModel = localStorage.getItem(`seclab_copilot_model_${engId.value}`)
    if (engModel) {
      copilotSelectedModel.value = engModel
      return
    }
    const defaultAuditModel = localStorage.getItem('seclab_default_audit_model')
    if (defaultAuditModel) {
      copilotSelectedModel.value = defaultAuditModel
      return
    }
  }
}

function onCopilotModelChange() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(`seclab_copilot_model_${engId.value}`, copilotSelectedModel.value)
    localStorage.setItem('seclab_default_audit_model', copilotSelectedModel.value)
  }
}

async function openContextInspection() {
  showContextModal.value = true
  injectedContextText.value = 'Generando contexto en tiempo real con pt-agent-context...'
  try {
    const res = await api.getCopilotContext(engId.value, selectedAgent.value, engType.value)
    injectedContextText.value = res.context || 'Sin contexto disponible.'
  } catch (err) {
    injectedContextText.value = 'Error al cargar contexto: ' + err.message
  }
}

function useQuickPrompt(text) {
  copilotInput.value = text
  sendCopilotMessage()
}

async function sendCopilotMessage() {
  if (!copilotInput.value.trim() || isCopilotThinking.value) return
  const userText = copilotInput.value.trim()
  copilotInput.value = ''

  copilotMessages.value.push({ role: 'user', content: userText })
  isCopilotThinking.value = true

  try {
    let reqProvider = null
    let reqModel = null
    let reqProfile = null

    if (copilotSelectedModel.value.startsWith('openrouter:')) {
      reqProvider = 'openrouter'
      reqModel = copilotSelectedModel.value.slice(11)
    } else if (copilotSelectedModel.value.startsWith('profile:')) {
      reqProfile = copilotSelectedModel.value.slice(8)
    } else if (copilotSelectedModel.value.includes(':')) {
      const separator = copilotSelectedModel.value.indexOf(':')
      const p = copilotSelectedModel.value.slice(0, separator)
      const m = copilotSelectedModel.value.slice(separator + 1)
      reqProvider = p
      reqModel = m
    } else {
      reqProfile = copilotSelectedModel.value
    }

    const payload = {
      engagement_id: engId.value,
      type: engType.value,
      agent_id: selectedAgent.value,
      messages: copilotMessages.value.map(m => ({ role: m.role, content: m.content })),
    }
    if (reqProvider) payload.provider = reqProvider
    if (reqModel) payload.model = reqModel
    if (reqProfile) payload.profile = reqProfile

    const res = await api.sendCopilotChat(payload)

    copilotMessages.value.push({
      role: 'assistant',
      content: res.content,
      model: res.model,
      provider: res.provider,
      latency_ms: res.latency_ms,
    })
  } catch (err) {
    copilotMessages.value.push({
      role: 'assistant',
      content: `[Error del Copiloto]: ${err.message}`,
      model: 'error',
    })
  } finally {
    isCopilotThinking.value = false
  }
}

function copyText(text) {
  if (!text) return
  navigator.clipboard.writeText(text)
  alert('Copiado al portapapeles: ' + text)
}

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

async function loadFlags() {
  try {
    const data = await api.getFlags(engId.value, engType.value)
    flagsData.value = {
      subtype: data.subtype || 'machine',
      category: data.category || 'misc',
      points: data.points ?? 100,
      difficulty: data.difficulty || 'medium',
      flag: data.flag || { value: '', status: 'pending', captured_at: null, notes: '' },
      user_flag: data.user_flag || { value: '', status: 'pending', captured_at: null },
      root_flag: data.root_flag || { value: '', status: 'pending', captured_at: null },
      custom_flags: data.custom_flags || [],
    }
  } catch (err) {
    console.error('Error al cargar banderas:', err)
  }
}

async function saveFlagsAction() {
  isSavingFlags.value = true
  try {
    await api.saveFlags(engId.value, flagsData.value, engType.value)
    await loadFlags()
  } catch (err) {
    alert('Error al guardar banderas: ' + err.message)
  } finally {
    isSavingFlags.value = false
  }
}

function toggleFlagStatus(flagType) {
  if (!flagsData.value[flagType]) {
    flagsData.value[flagType] = { status: 'pending', captured_at: null, value: '' }
  }
  if (flagsData.value[flagType].status === 'captured') {
    flagsData.value[flagType].status = 'pending'
    flagsData.value[flagType].captured_at = null
  } else {
    flagsData.value[flagType].status = 'captured'
    flagsData.value[flagType].captured_at = new Date().toISOString()
  }
}

async function loadLoot() {
  try {
    lootData.value = await api.getLoot(engId.value, engType.value)
  } catch (err) {
    console.error('Error al cargar botín:', err)
  }
}

async function submitCredential() {
  try {
    await api.saveCredential(engId.value, credForm.value, engType.value)
    showCredModal.value = false
    credForm.value = { service: 'SSH', host: '', port: 22, username: '', password: '', notes: '' }
    await loadLoot()
  } catch (err) {
    alert('Error al guardar credencial: ' + err.message)
  }
}

async function deleteCredAction(credId) {
  if (!confirm('¿Deseas eliminar esta credencial del botín?')) return
  try {
    await api.deleteCredential(engId.value, credId, engType.value)
    await loadLoot()
  } catch (err) {
    alert('Error al eliminar credencial: ' + err.message)
  }
}

async function selectArtifactFolder(folder) {
  activeArtifactFolder.value = folder
  selectedArtifact.value = null
  selectedArtifactContent.value = ''
  try {
    artifactFiles.value = await api.getArtifacts(engId.value, folder, engType.value)
  } catch (err) {
    console.error('Error al listar artefactos:', err)
    artifactFiles.value = []
  }
}

async function loadArtifactPreview(file) {
  selectedArtifact.value = file
  selectedArtifactContent.value = 'Cargando contenido...'
  try {
    const res = await api.getArtifactContent(engId.value, file.rel_path, engType.value)
    selectedArtifactContent.value = res.content
  } catch (err) {
    selectedArtifactContent.value = 'Error al leer archivo: ' + err.message
  }
}

async function loadReconStatus() {
  try {
    const res = await api.getReconStatus(engId.value, engType.value)
    reconStatus.value = res
    if (['running', 'cancelling'].includes(res.job?.status)) {
      startReconPolling()
    }
  } catch (err) {
    console.error('Error al cargar estado de recon:', err)
  }
}

async function loadReconLog() {
  try {
    const res = await api.getReconLog(engId.value, 300, engType.value)
    reconLogContent.value = res.content || ''
  } catch (err) {
    console.error('Error al cargar log de recon:', err)
  }
}

function startReconPolling() {
  if (reconPollTimer) return
  reconPollTimer = setInterval(async () => {
    await loadReconStatus()
    await loadReconLog()
    if (!['running', 'cancelling'].includes(reconStatus.value.job?.status)) {
      stopReconPolling()
    }
  }, 3000)
}

function stopReconPolling() {
  if (reconPollTimer) {
    clearInterval(reconPollTimer)
    reconPollTimer = null
  }
}

async function cancelReconPipeline() {
  isCancellingRecon.value = true
  reconActionMsg.value = ''
  try {
    const res = await api.cancelRecon(engId.value, engType.value)
    reconActionSuccess.value = true
    reconActionMsg.value = res.message
    await loadReconStatus()
    await loadReconLog()
    startReconPolling()
  } catch (err) {
    reconActionSuccess.value = false
    reconActionMsg.value = err.message || 'No se pudo cancelar el reconocimiento'
  } finally {
    isCancellingRecon.value = false
  }
}

async function triggerReconPipeline() {
  isStartingRecon.value = true
  reconActionMsg.value = ''
  try {
    const res = await api.runRecon(
      engId.value,
      { stage: reconStage.value, dry_run: reconDryRun.value },
      engType.value
    )
    reconActionSuccess.value = true
    reconActionMsg.value = res.message || 'Pipeline iniciado correctamente.'
    await loadReconStatus()
    await loadReconLog()
    startReconPolling()
  } catch (err) {
    reconActionSuccess.value = false
    reconActionMsg.value = err.message || 'Error al iniciar reconocimiento'
  } finally {
    isStartingRecon.value = false
  }
}

onMounted(() => {
  initCopilotModel()
  loadCopilotModels()
  loadScope()
  loadFindings()
  loadLogs()
  loadChecklist()
  loadNotes()
  loadReport()
  loadFlags()
  loadLoot()
  selectArtifactFolder('recon')
  loadReconStatus()
  loadReconLog()
})

onUnmounted(() => {
  stopReconPolling()
})
</script>

<style>
.prose-report {
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  color: #cbd5e1;
  line-height: 1.7;
}

.prose-report h1 {
  font-size: 1.75rem;
  font-weight: 800;
  color: #38bdf8;
  border-bottom: 2px solid #0284c7;
  padding-bottom: 0.5rem;
  margin-top: 1.5rem;
  margin-bottom: 1rem;
}

.prose-report h2 {
  font-size: 1.35rem;
  font-weight: 700;
  color: #38bdf8;
  border-bottom: 1px solid #1e293b;
  padding-bottom: 0.4rem;
  margin-top: 2rem;
  margin-bottom: 1rem;
}

.prose-report h3 {
  font-size: 1.15rem;
  font-weight: 700;
  color: #f1f5f9;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
}

.prose-report p {
  margin-bottom: 1rem;
}

.prose-report ul, .prose-report ol {
  margin-left: 1.5rem;
  margin-bottom: 1rem;
  list-style-type: disc;
}

.prose-report table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1.25rem;
  margin-bottom: 1.5rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.82rem;
}

.prose-report th {
  background-color: #0f172a;
  color: #38bdf8;
  padding: 0.6rem 0.75rem;
  border: 1px solid #1e293b;
  text-align: left;
  font-weight: 700;
}

.prose-report td {
  padding: 0.5rem 0.75rem;
  border: 1px solid #1e293b;
  color: #e2e8f0;
}

.prose-report tr:nth-child(even) td {
  background-color: #090e1a;
}

.prose-report pre {
  background-color: #050811;
  border: 1px solid #1e293b;
  border-radius: 0.375rem;
  padding: 1rem;
  overflow-x: auto;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  color: #38bdf8;
  margin-bottom: 1.25rem;
}

.prose-report code {
  font-family: ui-monospace, monospace;
  background-color: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 0.25rem;
  padding: 0.15rem 0.35rem;
  font-size: 0.85em;
  color: #38bdf8;
}

.prose-report hr {
  border: 0;
  border-top: 1px solid #1e293b;
  margin: 2rem 0;
}

@media print {
  body {
    background: #ffffff !important;
    color: #0f172a !important;
  }

  header, nav, footer, .no-print {
    display: none !important;
  }

  main {
    max-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  .tactical-card {
    background: #ffffff !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
  }

  .prose-report {
    color: #0f172a !important;
  }

  .prose-report h1 {
    color: #0369a1 !important;
    border-bottom: 2px solid #0284c7 !important;
  }

  .prose-report h2 {
    color: #0369a1 !important;
    border-bottom: 1px solid #cbd5e1 !important;
    page-break-before: always;
  }

  .prose-report h3 {
    color: #0f172a !important;
  }

  .prose-report table {
    width: 100% !important;
    border-collapse: collapse !important;
  }

  .prose-report th {
    background-color: #f1f5f9 !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
  }

  .prose-report td {
    border: 1px solid #cbd5e1 !important;
    color: #0f172a !important;
    background: #ffffff !important;
  }

  .prose-report tr:nth-child(even) td {
    background-color: #f8fafc !important;
  }

  .prose-report pre {
    background-color: #f8fafc !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
  }

  .prose-report code {
    background-color: #f1f5f9 !important;
    border: 1px solid #cbd5e1 !important;
    color: #0369a1 !important;
  }

  .prose-report hr {
    border-top: 1px solid #cbd5e1 !important;
  }
}
</style>
