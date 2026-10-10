# Fase 179: contexto indisponible bloquea la consulta IA

Fecha: 2026-10-10. V3-05d parcial. Rama `phase/179-copilot-context-gate`, base `297ccf0`, worktree `/Users/castr/tmp/t01-copilot-context-gate`.

## Problema y resultado

El runner devolvía stdout o stderr sin comprobar el código de salida del generador. Un fallo después de emitir texto parcial podía presentarse como contexto válido y alcanzar el proveedor IA; un timeout tampoco tenía tratamiento explícito. La regresión contra fase178 reproduce preview 200 con salida parcial de un proceso que terminó con código 7.

Preview y chat comparten ahora un gate antes de construir/enviar la consulta: el generador debe existir, iniciar y terminar correctamente en 15 segundos. Se acepta solo stdout UTF-8 no vacío, sin NUL y de hasta 256 KiB. Falta, fallo, timeout, error de inicio/decodificación o contenido inválido devuelve 503 con mensaje seguro de disponibilidad. Stderr, trazas, rutas y salida parcial no sustituyen contexto ni se envían al proveedor. Un contexto válido conserva exactamente su stdout y el flujo habitual de proveedor/modelo.

La vista conserva el error y la alternativa de orientación local de fase178. El inspector liga cada respuesta a solicitud, proyecto/tipo y especialidad; cambiar cualquiera cierra y limpia el modal. Respuestas tras cierre, cambio o desmontaje se descartan.

## Verificación

237 Python, 220 backend, 141 frontend/audit 0, 4 UI y 5 integraciones Chromium aprobados. Cinco pruebas nuevas de backend cubren proceso real no-cero con stdout parcial/stderr, generador ausente sin inicio, timeout/OSError/UTF-8 inválido, contenido vacío/NUL/excesivo y contexto válido preservado. Preview/chat se prueban con proveedor AsyncMock: no se llama ante bloqueo; contexto válido llega sin stderr. Contra las fuentes fase178 fallan estas regresiones; log `baseline-backend-final.log` conserva preview 200 con salida parcial. Primer intento sin allowed host testserver no fue reproducción válida; el segundo corregido es la evidencia.

Cuatro pruebas nuevas Vue cubren respuestas tardías al cambiar proyecto/tipo/especialidad y error con orientación local. La integración reusa sesión existente y proyecto copilot-local sintético de fase178, Vault vacío, tester/read-only/sin red. Bytes inválidos en live_hosts.txt hacen fallar el generador instalado: preview/chat 503 sin trazas, panel local mantiene el job bloqueado sin comando. Scope por bytes, historial y job no cambian. Restaurar el archivo recupera contexto 200. Capturas `copilot-context-unavailable.png` y `copilot-context-local-fallback.png` inspeccionadas y conservadas junto con logs en `tmp/phase179` del checkout principal.

Imagen aislada `seclab-sbf:full-phase179`, build-inputs `afd056372ace36a6`, ID `sha256:b0802a05924dddba2f2f30ef407e8d4e6c579ca5f906bb372f820b2cf538a0e5`, igual al checkout. Base existente phase172 reutilizada tras comprobar hash `f772cb17ffe418a0`; sin reconstruirla ni publicar. Build, smoke (cuatro manifiesto, ocho UUID, 21 checkpoint), Compose local/inside y Actionlint aprobados. Gate High/Critical aprobado bajo política existente sin nuevas excepciones/dependencias.

SBOM CycloneDX 1.7 válido, 2251 componentes, `tmp/phase179/sbom/seclab-sbf-full-phase179-afd056372ace36a6.json`, SHA-256 `d69b8b9d1361c2131db31986b39c281f32a7993046b6195f657916957d138a38`. PR y CI del head exacto requeridos antes del merge; autorización vigente hasta 2026-10-11 16:43:06 UTC. Sin publicar/desplegar ni modificar proyectos del owner.

## Límites y compatibilidad

No cambia el CLI del generador, el selector de proveedor/modelo, las reglas de alcance ni los archivos de los proyectos. Un fallo requiere corregir/reintentar o usar la orientación local; no selecciona otro contexto ni reintenta IA. El límite de 256 KiB valida el contenido capturado: no es un límite duro de memoria del subprocess. El timeout cubre el proceso generador; no acredita integridad semántica, suficiencia de evidencia ni disponibilidad de cada fuente que el generador tolere omitir. El contexto válido puede seguir incluyendo información privada: revisión/redacción y citas siguen pendientes. V3-05 y V3 global continúan parciales.
