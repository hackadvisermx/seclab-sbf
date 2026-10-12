# Fase 215: Matriz extendida de evaluación de alcance y normalización de activos

Fecha: 2026-10-12 UTC. Rama `phase/215-scope-matcher-matrix`, base `71b1c27`. V3-01f parcial.

## Problema y cambio

El contrato ejecutable de autorización y alcance (V3-01) debe garantizar de forma determinista que ninguna acción de reconocimiento, interacción activa o copiloto actúe sobre activos fuera de alcance debido a discrepancias en el análisis sintáctico de objetivos.

Existían riesgos potenciales y casos de borde en:
1. Normalización y correspondencia de dominios IDNA / Punycode (p. ej. `xn--bcher-kva.de` frente a `bücher.de`, `испытание.рф`): riesgo de evasión por discrepancia de codificación entre representaciones Unicode y ASCII.
2. Fronteras estrictas de comodines y subdominios: asegurar que `*.target.local` coincida únicamente con subdominios legítimos (`sub.target.local`, `deep.sub.target.local`), rechazando colisiones sintácticas (`faketarget.local`, `target.local.attacker.com`, `attacker-target.local`) y diferenciando dominios apex (`target.local`).
3. Matriz exhaustiva IPv6 y CIDRs: soporte de representaciones canónicas comprimidas, no comprimidas (`2001:0db8::1`), direcciones IPv6 entre corchetes (`[2001:db8::1]`), puertos explícitos y precedencia estricta de exclusión (`out_of_scope`).
4. Normalización de Endpoints y mitigación de Path Traversal: `endpoint_matches` permitía que rutas con secuencias relativas `..` (como `/api/../admin`) pudieran coincidir con reglas prefijadas `/api/`.
5. Extracción de candidatos desde texto libre (`extract_candidate_targets` en `pt-scope-validator.py`): no extraía direcciones IPv6 ni dominios internacionales (IDNA) en respuestas generadas por modelos de lenguaje.
6. Compatibilidad de TestClient Starlette en backend (`app/config.py`): inclusión de `testserver` en `ALLOWED_HOSTS` por defecto, permitiendo pruebas unitarias del backend sin requerir variables de entorno adicionales.

En esta fase:
1. Motor de alcance (`scripts/seclab_scope.py`):
   - Soporte y normalización para direcciones IPv6 entre corchetes en `is_ip` y `normalize_target`.
   - Normalización de rutas con `posixpath.normpath` en `endpoint_matches`: resolución de `..` y `.` previa a la comprobación de prefijos, neutralizando ataques de path traversal hacia endpoints no autorizados.
   - Preservación y verificación estricta de dominios IDNA / Punycode y fronteras de comodines.
2. Extracción de objetivos de texto libre (`scripts/pt-scope-validator.py`):
   - Regex `_IPV6_RE` y validación canónica con `ipaddress.IPv6Address` para extraer IPv6 sueltas o entre corchetes.
   - Soporte para etiquetas IDNA en `_HOST_RE`.
3. Simulación de plantillas en Playbooks (`scripts/seclab_playbook.py`):
   - Soporte determinista en `run_playbook` para previsualización y dry-run de plantillas de catálogo sin requerir `target.yaml`.
4. Pruebas y verificación:
   - Nueva suite `scripts/verify/test_seclab_scope_matrix.py` con 5 pruebas exhaustivas.
   - Integración en el runner `scripts/verify/check-python-units.py` (298 pruebas totales aprobadas).
   - 169 pruebas frontend aprobadas en Vitest.

## Verificación y límites

- 298 pruebas Python unitarias aprobadas en host (`check-python-units.py`).
- 169 pruebas frontend unitarias aprobadas en Vitest (`npm test`).
- V3-01f parcial: fortalece la matriz de evaluación de alcance, normalización IDNA/IPv6 y neutralización de evasiones de path traversal en endpoints.
