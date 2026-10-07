# Experiencia guiada de auditoría para principiantes

Fecha: 2026-10-07. Base revisada: `fa5c310`. Primera entrega: fase 143, rama `phase/143-guidance-contracts`. Este plan complementa el backlog A1–A21 ya cerrado; no lo reabre.

## Objetivo y límites

Una persona que conoce su dominio autorizado debe poder saber qué hacer, por qué, qué resultado guardar y cuál es el siguiente paso. El caso principal es una auditoría web de un dominio público autorizado; los retos CTF conservan un recorrido separado. La cobertura expresa trabajo documentado, nunca una garantía de ausencia de vulnerabilidades.

La IA ayuda a interpretar evidencias, explicar pruebas y proponer pasos. Los playbooks describen procedimientos, requisitos, límites y resultados esperados. El operador confirma el alcance, decide ejecutar, valida hallazgos y aprueba el reporte. Configurar una IA no debe ser requisito para completar el recorrido.

## Registro del diagnóstico

| ID | Problema observado | Entrega prevista |
| --- | --- | --- |
| U1 | El panel lee `recommendation`, pero la CLI emite `next_step`; `-j -p` omitía el prompt. | Fase 1 |
| U2 | Guía con comandos incorrectos: dominio posicional en `pt-eng new`, argumento extra en `pt-scope check`, subcomandos inexistentes de callback y nombre incorrecto del archivo de hosts vivos. | Fase 1 |
| U3 | Crear un proyecto añadía alcance de ejemplo o comodines sin confirmación; omitir el alcance permitía continuar hacia recon. | Fase 1 |
| U4 | Cobertura inferida por palabras clave, hallazgos o marcador de disciplina; no registra cada prueba, activo o rol. | Fase 3 |
| U5 | El Copiloto no integra uniformemente el playbook completo, notas y catálogo de proveedores del Chat. | Fase 5 |
| U6 | `pt-nmp` usa un escaneo amplio y rápido; no es una receta predeterminada adecuada para todo dominio público. | Fase 4 |

## Entregas, dependencias y aceptación

| Fase | Estado | Cambio y aceptación |
| --- | --- | --- |
| 1. Contratos y alcance | Implementación en revisión (143) | Recomendación y prompt visibles; comandos conocidos válidos; dominio exacto o IP sin objetivos inventados; alcance vacío exige revisión; omitir confirmación abre el detalle sin lanzar recon. |
| 2. Asistente persistente | Pendiente; depende de 1 | Guardar y retomar progreso. Recoger autorización, ventanas, contactos, exclusiones, límites, usuarios/roles y requisitos del objetivo. Distinguir pasos completos, pendientes y bloqueados. Recargar no pierde el estado. |
| 3. Matriz de pruebas | Pendiente; depende de 2 | Casos por activo y rol: pendiente, probado sin hallazgo, hallazgo candidato/confirmado, no aplicable con motivo y bloqueado. Cada resultado conserva evidencia o explicación; no se completa una disciplina solo por un hallazgo. |
| 4. Playbooks guiados | Pendiente; depende de 2–3 | Cada paso explica objetivo, prerrequisitos, entradas, límites, comando revisable y salida esperada. Enlaza artefactos reales. Rechaza objetivos fuera del alcance y evita escaneos intensivos por defecto. No exige rediseñar todas las herramientas. |
| 5. IA contextual | Pendiente; depende de 3–4 | Resolver agente → playbook completo y añadir notas relevantes. Seleccionar proveedor/modelo consistentemente. Mostrar contexto saliente revisable, advertencias de alcance y limitaciones; sin ejecución autónoma. Recorrido completo también sin IA. |
| 6. Hallazgos y cierre | Pendiente; depende de 3–5 | Guiar candidato → prueba → control negativo → confirmado, severidad y remediación. Revisar duplicados, límites, pruebas faltantes, limpieza y retest. Reporte distingue riesgo actual de evidencia descartada o histórica. |
| 7. Onboarding y navegación | Pendiente; depende de 2–6 | Inicio con «Auditar dominio» / «Resolver CTF», ayuda contextual y errores con acción de recuperación. Prueba de usuario nuevo: crear, pausar, retomar, documentar y cerrar sin depender de memorizar comandos. |

Cada fase debe tener su PR, criterios comprobables y documentación propia. No combinar toda la tabla en una sola issue ni incorporar deuda ajena a esos criterios.

## Recorrido previsto: tengo un dominio

1. Registrar autorización y dominio exacto. Confirmar si los subdominios están autorizados: autorizar `example.com` no autoriza `*.example.com`. Registrar exclusiones, proveedores ajenos, ventanas y límites.
2. Crear el proyecto y revisar su alcance. Simular reconocimiento antes de emitir tráfico. Revisar que las herramientas y límites sean adecuados al objetivo.
3. Ejecutar reconocimiento autorizado y revisar activos, hosts vivos, URLs y tecnologías. Los activos descubiertos no se autorizan automáticamente; actualizar alcance solo con autorización explícita.
4. Definir la matriz aplicable: configuración, autenticación, autorización entre roles, sesiones, entradas/inyecciones, lógica de negocio y demás disciplinas relevantes. Registrar razones para lo que no aplica.
5. Elegir un playbook por prueba. Comprender su propósito, cumplir requisitos y ejecutar de forma acotada. Guardar también resultados negativos y bloqueos.
6. Consultar opcionalmente la IA para interpretar la evidencia y proponer el próximo paso. Revisar contexto y alcance antes de enviar; verificar su propuesta con el playbook y la evidencia real.
7. Validar candidatos con reproducción y control negativo cuando corresponda. Guardar petición/respuesta, impacto, activo, rol y remediación; consolidar causas raíz repetidas.
8. Revisar matriz, limitaciones, reporte, limpieza y retest. Declarar lo no probado; cerrar formalmente cuando se cumplan los criterios acordados.

Los pasos 4–8 describen la experiencia objetivo. La aplicación actual mantiene cobertura heurística y herramientas avanzadas; la fase 143 no entrega aún esa matriz ni automatiza toda la auditoría.

## Fase 143: comportamiento implementado

- `seclab_scope.initial_scope` comparte la creación conservadora entre backend y `pt-eng`. Sin objetivo crea listas vacías; con dominio exacto o IP incluye solo ese valor. Un comodín debe proporcionarse explícitamente. Una URL en el campo dominio falla antes de crear carpetas.
- No se siembran `/api`, subdominios, IP de ejemplo, exclusiones ni referencias ficticias de autorización/contacto. Los proyectos existentes no se migran ni se amplían.
- El wizard permite editar dominios, IP/CIDR y exclusiones de dominios. Exige confirmación y al menos un objetivo antes del paso de reconocimiento. «Guardar proyecto y revisar después» abre el detalle. Esta confirmación cubre el wizard; no es un bloqueo global de todas las herramientas de terminal.
- `pt-next` prioriza revisar alcance ausente, inválido o vacío. JSON conserva `next_step`; combinar `--json --prompt` añade `prompt`. El panel muestra título, motivo y comando copiable. Generar prompt no llama a un proveedor ni ejecuta comandos.
- Ambas copias de la guía HTML y `pt-guide` usan `--domain`, la firma real de `pt-scope check`, `pt-callback start/show` y `recon/live_hosts.txt`. El generador empieza con `--dry-run` y rechaza entradas capaces de producir instrucciones o HTML arbitrarios. Ese generador admite dominio o IPv4; IPv6 puede configurarse en el editor/CLI de proyecto.

### Uso inmediato

En dashboard: **Nueva Auditoría → nombre y dominio → editar alcance/exclusiones → confirmar → simular recon**. Para dejarlo pendiente, guardar y revisar después. En el detalle, abrir **Metodología & Cobertura** para ver la recomendación y generar el prompt.

En terminal, dentro del contenedor:

```sh
pt-eng new auditoria-demo --domain example.com
cd /workspace/engagements/auditoria-demo
pt-scope show
pt-scope check https://example.com
pt-recon auditoria-demo --dry-run
pt-next --json --prompt
```

Sustituir el ejemplo por un objetivo autorizado. Editar y revisar `target.yaml` antes de ejecutar el reconocimiento real. Para autorizar subdominios explícitamente, añadir la regla `*.example.com` solo si está permitida. No interpretar una simulación como reconocimiento ejecutado.

## Verificación y límites de la entrega

El registro de comandos, resultados y riesgos de esta entrega se mantiene en [phase-143.md](phase-143.md). La aceptación requiere regresiones del contrato de prompt, creación de alcance, wizard y comandos de guía, además de comprobación real en navegador y CLI. Los gates no reemplazan una auditoría real ni verifican proveedores externos con claves reales.

Reversión: revertir el PR de fase 143 y reconstruir una imagen aislada. No modificar automáticamente proyectos ya creados; sus alcances requieren decisión del operador. Una imagen construida no actualiza el contenedor en ejecución.
