# Fase 68: Scaffolding de Engagements (`pt-eng`) y Validador de Scope en Tiempo Real (`pt-scope`)

## 1. Contexto y Objetivos

Para elevar la disciplina operativa, la gobernanza del alcance y la trazabilidad forense en `seclab-sbf`, esta fase implementa un sistema unificado de gestión de pruebas de intrusión y control determinista de límites:

1. **Especificación Formal de Alcance (`target.yaml`)**:
   - Manifiesto declarativo estructurado en formato YAML ubicado en la raíz de cada engagement (`/workspace/engagements/<nombre>/target.yaml`).
   - Define formalmente activos autorizados (`in_scope`: dominios, comodines, direcciones IP, bloques CIDR y endpoints REST).
   - Establece exclusiones estrictas (`out_of_scope`: dominios de terceros, IPs críticas de producción, notas de restricción).
   - Registra parámetros operativos obligatorios (`operational_limits`: tasa de peticiones por segundo, hilos paralelos, prohibición de DoS o ingeniería social).

2. **Motor de Validación de Alcance en Tiempo Real (`pt-scope` / `pt-scope-validator`)**:
   - Binario ejecutable en Python (`/usr/local/bin/pt-scope-validator`) sin dependencias externas obligatorias (usa la biblioteca estándar `ipaddress` y parser YAML integrado con soporte opcional de PyYAML).
   - Normalización de URLs, esquemas (`http`/`https`), puertos y rutas a hostnames limpios o IPs.
   - Algoritmo de decisión con **precedencia de exclusiones**: las listas `out_of_scope` se evalúan antes de cualquier coincidencia positiva, garantizando que IPs específicas dentro de bloques CIDR autorizados o subdominios excluidos sean rechazados de inmediato con código de salida 1.
   - Evaluación jerárquica de subdominios y comodines (`*.example.com` cubre `api.example.com` y `deep.sub.example.com`).

3. **Scaffolding y Orquestación Automatizada (`pt-eng`)**:
   - Helper interactivo en Zsh (`pt-eng` con alias `pteng` y `engagement`).
   - Generación de estructura estándar de carpetas: `recon/`, `fuzzing/`, `evidence/`, `loot/` y `screenshots/`.
   - Siembra automatizada con sustitución de variables de `target.yaml`, `scope.txt` y `notes.md` a partir de las plantillas en `workspace-seed/templates/`.
   - Vinculación automática con el sistema de auditoría continua `pt-log` bajo tmux.
   - Métricas y monitoreo con `pt-eng list` y `pt-eng status`.

---

## 2. Componentes e Implementación

### 2.1 Plantilla de Alcance (`workspace-seed/templates/target.yaml`)
Define el esquema estándar:
- `engagement`: Metadatos del cliente, auditor, contacto de emergencia y referencia legal (ToS / reglas de Bug Bounty).
- `network`: Perfil VPN asociado (`tryhackme`, `hackthebox`, `client`, `none`) y gateway.
- `scope.in_scope`: Lista de dominios (`domains`), direcciones IP (`ips`), bloques (`cidrs`) y URLs (`endpoints`).
- `scope.out_of_scope`: Lista de activos excluidos explícitamente.
- `operational_limits`: Restricciones de peticiones por segundo (`max_requests_per_second`), hilos (`max_parallel_threads`) y banderas booleanas para DoS e ingeniería social.

### 2.2 Motor de Validación (`scripts/pt-scope-validator.py`)
- Valida cadenas individuales contra el archivo de configuración activo del engagement o el directorio de trabajo actual.
- Comandos soportados:
  - `pt-scope-validator check <config_o_dir> <target>`: Retorna `0` (IN_SCOPE), `1` (OUT_OF_SCOPE) o `3` (UNKNOWN).
  - `pt-scope-validator show <config_o_dir>`: Despliega una tabla consolidada en terminal con activos autorizados y exclusiones.

### 2.3 Funciones de Shell (`shell/pentest-lab/pentest-lab.plugin.zsh`)
- `pt-eng new <nombre> [--domain dominio] [--type engagement|reto]`: Inicializa el engagement, valida nombres mediante regex alfanumérica contra *path traversal*, siembra plantillas e inicia `pt-log`.
- `pt-eng list`: Muestra tabla con engagements activos, cantidad de evidencias `.md`, líneas registradas en `terminal.log` y presencia de reglas de scope.
- `pt-eng status [nombre]`: Inspección detallada del estado del engagement.
- `pt-scope check <target>`: Wrapper ergonómico que resuelve automáticamente el archivo de configuración a partir del engagement activo o el directorio actual.
- `pt-scope show`: Muestra la matriz de alcance del engagement activo.
- Aliases: `pteng`, `engagement`, `ptscope`, `scopecheck`.

---

## 3. Pruebas y Validación

1. **Pruebas Unitarias Python (`scripts/verify/check-python-units.py`)**:
   - `test_engagement_scaffolding_and_scope_guard`: Valida parsing de `target.yaml`, normalización de URLs, resolución de comodines, precedencia de exclusión sobre CIDRs (p. ej., `192.0.2.254` excluida dentro del bloque `192.0.2.0/24`) y presencia de helpers en el plugin y Dockerfile.
   - `test_pentest_lab_plugin_helpers_and_aliases`: Valida helpers (`pt-eng()`, `pt-scope()`), aliases (`pteng`, `engagement`, `ptscope`, `scopecheck`) y textos en `pt-help`.
   - Total: **57/57 pruebas en verde**.

2. **Suite de Calidad (`make verify`)**:
   - Gitleaks (0 secretos encontrados).
   - Hadolint (Dockerfiles limpios).
   - ShellCheck y Actionlint en verde.
   - Validación de configuración de Compose (`make compose-config`).
