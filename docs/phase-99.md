# Fase 99 — Actualización Integral de la Guía del Operador e Integración en el Dashboard Web

Actualización de la guía interactiva y visual del operador ([`docs/guia-laboratorio.html`](file:///Users/castr/tmp/t01/docs/guia-laboratorio.html) y [`workspace-seed/guia.html`](file:///Users/castr/tmp/t01/workspace-seed/guia.html)) para reflejar todas las capacidades recientes de SecLab (CTF Jeopardy, compuertas de evidencia Bug Bounty, Hermes API Vault, Centro de Mando Web, telemetría de red y catálogo ampliado a 100+ herramientas) e integración directa en la vista de Ayuda del Dashboard ([`HelpView.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/views/HelpView.vue)) mediante endpoint dedicado en [`help_center.py`](file:///Users/castr/tmp/t01/dashboard/backend/app/api/endpoints/help_center.py).

## Diagnóstico y Objetivos

1. **Desfase en la Guía de Laboratorio (`guia-laboratorio.html`)**:
   - La guía interactiva original no reflejaba los avances de las últimas fases:
     - Falta de soporte para retos CTF Jeopardy (`subtype: "jeopardy"`, flags `flag{...}`, categorías técnicas, puntuación y writeups).
     - Falta de la metodología Evidence-First y compuertas de bug bounty hunting: Credential-Validation Gate con Control Negativo (Paso 2b / Paso 6), enrutamiento por Modo de Acceso (`RICH`, `PARTIAL`, `UNAUTH`), Bounded Non-Destructive Testing (BDT) y ciclo de estados formal (`PROVEN`, `CANDIDATE`, `DISPROVED`, `MITIGATED`).
     - Ausencia de documentación sobre el Hermes API Key Vault (cifrado AES-256-GCM para OpenAI, Anthropic, Gemini, Groq, Ollama) y su puente CLI `pt-vault-bridge`.
     - Ausencia del Centro de Mando Web (Dashboard en `:8080`), Terminal Web multi-tab en `:7681`, telemetría de IPs en tiempo real en la barra de navegación y la papelera atómica `.seclab-trash`.
     - Catálogo de herramientas interactivo limitado a solo 19 utilidades básicas frente a las más de 100 herramientas instaladas en la imagen del laboratorio (`gau`, `findomain`, `assetfinder`, `httprobe`, `gf`, `qsreplace`, `x8`, `wpscan`, `nikto`, `bettercap`, `s3scanner`, `ligolo`, `chisel`, `pspy`, `zsteg`, `exiftool`, `gdb-multiarch` con GEF, etc.).

2. **Acceso a la Guía desde el Dashboard Web**:
   - El menú "Ayuda & Acceso" ([`HelpView.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/views/HelpView.vue)) ofrecía pestañas para "Datos de Acceso & Red", "Catálogo pt-cheat" y "Playbooks de Habilidades (skills/)", pero carecía de la guía interactiva del operador.
   - La API de ayuda carecía de un endpoint para servir el archivo `guia.html` con las cabeceras y control de acceso adecuados.

## Solución Técnica

1. **Actualización de la Guía del Operador (`docs/guia-laboratorio.html` & `workspace-seed/guia.html`)**:
   - **Metadatos y Cabecera**: Badges actualizados a `100+ Herramientas`, `10 Agent Skills`, `8 Disciplinas`, `Scope Guard & BDT`, `Evidence-First`.
   - **Selector de Misiones**: Incorporación de 5 misiones operativas completas:
     1. `🌐 Auditoría Web / API`: Scope Guard, BDT (1-3 reqs), Credential Gate y reportes ejecutivos.
     2. `🏁 Reto CTF / Máquina`: Retos Jeopardy por categorías (`web`, `crypto`, `pwn`, `reverse`, `forensics`, `misc`, `osint`) con banderas `flag{...}`, o Máquinas de laboratorio (HTB/THM) con VPN túnel (`vpntry`/`vpnhtb`), `pt-log` y banderas de usuario/root.
     3. `🤖 Orquestar con IA / Agentes`: Hermes API Vault (AES-256-GCM), Copiloto táctico, subagentes enriquecidos, `pt-context` y `pt-next --prompt`.
     4. `🔀 Pivoting & Redes`: Túneles SOCKS5 (`pt-socks`), reenvío TCP (`pt-forward`), Ligolo/Chisel, Proxychains y servidor de staging `pt-serv-payloads`.
     5. `💻 Centro de Mando Web & Telemetría`: Dashboard táctico en `:8080`, Terminal Web multi-tab en `:7681`, chips de IP local/VPN en vivo y papelera `.seclab-trash`.
   - **Compuertas de Calidad Bug Bounty en Paso 5**:
     - *Credential Gate*: Control Negativo obligatorio antes de reportar tokens/API keys.
     - *Modos de Acceso*: `RICH` (IDOR bidireccional cruzado), `PARTIAL` (BFLA y mutación propia), `UNAUTH` (pre-auth y fugas en SPAs).
     - *Estándar BDT*: Límite de 1-3 peticiones de prueba y reversión de mutaciones.
     - *Ciclo de Vida*: Estados `PROVEN`, `CANDIDATE`, `DISPROVED`, `MITIGATED`.
   - **Base de Datos de Herramientas Ampliada**:
     - Más de 40 herramientas esenciales indexadas con comandos rápidos de copia y filtrado por categoría y descripción en tiempo real.
   - **Invariante de Replicación Bit a Bit**:
     - `workspace-seed/guia.html` sincronizado de forma idéntica con `docs/guia-laboratorio.html` para garantizar la aprobación estricta de `scripts/verify/check-python-units.py`.

2. **Resolución y Servicio Backend (`config.py` & `help_center.py`)**:
   - `_resolve_guide_html_file()` en [`config.py`](file:///Users/castr/tmp/t01/dashboard/backend/app/config.py): Resolución defensiva multi-candidato (`/workspace/guia.html`, `/usr/local/share/seclab/guide/index.html`, `docs/guia-laboratorio.html`, `workspace-seed/guia.html`).
   - Endpoint autenticado `GET /api/v1/help/guide` en [`help_center.py`](file:///Users/castr/tmp/t01/dashboard/backend/app/api/endpoints/help_center.py): Sirve la guía en `HTMLResponse` con protección de sesión `require_operator`, `Cache-Control: no-store` y prevención de enlaces simbólicos inseguros.

3. **Integración Frontend en el Dashboard (`HelpView.vue` & `api.js`)**:
   - Pestaña predeterminada `'guide'` ("Guía del Operador") en [`HelpView.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/views/HelpView.vue).
   - Panel de resumen con 5 tarjetas tácticas de misión (`Misión 1` a `Misión 5`).
   - Contenedor táctico con visor interactivo en `<iframe>` embebido apuntando a `/api/v1/help/guide`.
   - Controles de "↗ Pantalla Completa" (abre `/api/v1/help/guide` en pestaña independiente) y "↻ Recargar" para refrescar el marco.
   - Ayudante `getGuideUrl()` en [`api.js`](file:///Users/castr/tmp/t01/dashboard/frontend/src/api.js).

4. **Sincronización en Espacio de Trabajo (`Makefile`)**:
   - Target `workspace-dir` asegura la existencia de `guia.html` en workspaces preexistentes copiándolo desde `workspace-seed/guia.html` si está ausente.

## Validación y Cobertura

- **Frontend Tests**: 20 pruebas aprobadas (+2 nuevas en [`help-guide.test.js`](file:///Users/castr/tmp/t01/dashboard/frontend/tests/help-guide.test.js)):
  - Renderizado predeterminado de la pestaña Guía del Operador con iframe y enlace a pantalla completa.
  - Navegación fluida entre pestañas de Guía, Accesos, Cheatsheet y Skills.
- **Auditoría npm**: 0 vulnerabilidades (`npm run audit`).
- **Compilación Frontend**: Build exitoso con Vite (`npm run build`).
- **Backend Tests (`make dashboard-tests`)**: 68 pruebas aprobadas (+3 nuevas en [`test_help_guide.py`](file:///Users/castr/tmp/t01/dashboard/backend/tests/test_help_guide.py)):
  - Retorno 401 en accesos no autenticados a `/api/v1/help/guide`.
  - Retorno 200 con `text/html` y contenido completo en accesos autenticados.
  - Retorno 404 seguro si el archivo de la guía falta o es un symlink.
- **Regresión Completa (`make verify`)**: 117 pruebas aprobadas (incluyendo la verificación estricta de igualdad entre `docs/guia-laboratorio.html` y `workspace-seed/guia.html`).
- **Análisis de Secretos (`gitleaks`)**: 0 leaks encontrados.
