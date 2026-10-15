# Fase 255 — Actualización Integral de la Guía del Operador (`docs/guia-laboratorio.html` y `workspace-seed/guia.html`)

## Resumen Ejecutivo

- **ID de Mejora:** Documentación Táctica & Asistencia Interactiva del Operador (Fase 255).
- **Objetivo:** Actualizar integralmente la guía interactiva y visual del operador (`docs/guia-laboratorio.html` y su réplica idéntica en `workspace-seed/guia.html`) para reflejar todas las capacidades del ecosistema SecLab-SBF desarrolladas en las versiones V3 recientes:
  1. **Playbooks Deterministas de Seguridad (V3-04 & Fases 244-254):**
     - Catálogo estructurado de playbooks YAML (`web_owasp_top10.yaml`, `api_graphql_audit.yaml`, `oauth_jwt_audit.yaml`, `smb_shares_recon.yaml`, `internal_pivot_audit.yaml`).
     - Procedimiento de ejecución simulada (dry-run) y ejecución interactiva paso a paso (`/step/run`, botón «▶️ Paso»).
     - Salvaguardas fail-closed integradas con Scope Guard (código 126, BLOCKED), precedencia estricta de banderas de destino (`--proxy`, `-x`, `-connect`), y semántica dependiente del binario (`curl -F` vs `nmap -F`).
  2. **Copiloto Táctico Local & Multi-Proveedor con Fallback Heurístico (V3-05):**
     - Integración con modelos locales (Ollama en `:11434`, vLLM en `:8000`) y proveedores cloud vía Hermes Vault (AES-256-GCM).
     - Healthcheck en vivo de proveedores con botón interactivo «🔌 Estado Local» y píldora reactiva.
     - Fallback heurístico offline determinista con cero pérdida de estado ante caídas del proveedor local.
     - Registro inmutable de consentimiento y auditoría en `evidence/.copilot_consent.jsonl` y exportación estructurada de transcripciones del chat con verificación de citas en disco.
  3. **Supervisión Pedagógica Continua & Autorreflexión (V3-06):**
     - Checkpoints formativos automáticos vinculados al ciclo de vida del engagement.
     - Formulario interactivo de autorreflexión y justificación pedagógica de decisiones por parte del estudiante.
     - Vista agregada de supervisión pedagógica para cohortes docentes y aulas (`/cohort/summary`).
     - Exportación de informes pedagógicos en Markdown y JSON.
  4. **Métricas Operacionales Longitudinales & Calidad de Auditoría (V3-07):**
     - Historial temporal longitudinal y snapshots periódicos en `evidence/.metrics_history.jsonl`.
     - 4 pilares de madurez técnica: Scope Rigor, Evidence-First Quality, Methodological Coverage y Reporting Readiness.
     - Resumen global cross-engagement para todo el workspace.
  5. **Trazabilidad Técnica & Grafo de Procedencia DAG (V3-02s & V3-02r):**
     - Grafo estructurado DAG correlacionando alcance (`target.yaml`), escaneos (`recon_jobs.db`), hallazgos (`evidence/*.md`) y entregables (`REPORT.md`, `artifact-manifest.json`).
     - Exportación a formato Mermaid y JSON.
     - Ingestión de corridas CLI manuales y externas en `recon_jobs.db` con badge visual `CLI_EXTERNAL`.
  6. **Scope Guard DNS Drift & Revisiones Inmutables (V3-01):**
     - Detección de desvío DNS (`/dns-drift`) antes de despachar herramientas activas.
     - Registro inmutable de revisiones y diffs unificados de `target.yaml`.
     - Tarjeta táctica de fronteras técnicas y límites operacionales frente a la terminal web `ttyd`.
  7. **Exportación Estándar OASIS SARIF v2.1.0 & Firma Criptográfica (V3-03):**
     - Exportación de hallazgos en formato SARIF v2.1.0 para integración con pipelines CI/CD y GitHub Code Scanning.
     - Firma criptográfica y sellado de no repudio para `artifact-manifest.json`.
     - Conmutador reactivo de redacción de secretos en el visor modal de artefactos.
  8. **Centro de Mando Web, Buscador y Tema Dual:**
     - Soporte para modo oscuro táctico y modo claro (`@media (prefers-color-scheme: light)`).
     - Buscador ampliado de herramientas incorporando utilidades CLI (`seclab-playbook`, `seclab-metrics`, `seclab-supervision`, `seclab-provenance`, `seclab-sarif`, `seclab-signature`, `seclab-copilot-export`, `seclab-record-job`).
- **Archivos modificados:**
  - `docs/guia-laboratorio.html`: Actualización visual, metodológica, selector de misiones, tarjetas de dashboard y catálogo de herramientas.
  - `workspace-seed/guia.html`: Sincronización idéntica byte por byte requerida por `scripts/verify/check-python-units.py`.
- **Verificación:**
  - `check-python-units.py`: 357 pruebas unitarias aprobadas (verificando igualdad estricta de `guia.html`).
  - `dashboard/backend/tests/test_help_guide.py`: 3/3 pruebas aprobadas.
  - Pruebas frontend: 193/193 pruebas aprobadas en Vitest.
  - `git diff --check`: Salida limpia, cero advertencias de formato o espacios en blanco sobrantes.
