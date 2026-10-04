---
name: duplicate-scope-guard
description: Compuerta de auto-verificación previa al reporte para descartar hallazgos duplicados, falsos positivos o excluidos por la política del programa.
version: 1.0.0
author: hackadvisermx/seclab-sbf
license: MIT
category: guard
tools:
  - view_file
  - curl
  - pt-log
---

# Skill: Self-Duplicate & Out-of-Scope Policy Guard (`duplicate-scope-guard`)

## 1. Propósito y Alcance

Inspirada en las **Fases 08 y 10 de mdpsec/bug-bounty-hunting-prompts**, esta habilidad constituye la última línea de defensa contra reportes de baja calidad, duplicados evidentes y hallazgos excluidos por las políticas del programa.

Su objetivo es proteger la reputación del auditor y el tiempo del equipo de seguridad evitando:
- Enviar hallazgos que no representan un riesgo de seguridad tangible.
- Reportar problemas expresamente prohibidos o fuera de alcance en las reglas de engagement.
- Duplicar vulnerabilidades ampliamente conocidas o reportadas en divulgaciones públicas previas.

---

## 2. Precondiciones y Guardrails (Lista Negra de No-Issues)

El agente **DEBE RECHAZAR AUTOMÁTICAMENTE** la inclusión en el informe de los siguientes temas, a menos que formen parte integral de una cadena de explotación con impacto crítico demostrado:

| Categoría | Motivo de Rechazo / Exclusión Habitual |
|---|---|
| **Self-XSS** | Requiere que el usuario pegue código manualmente en su consola o solo se afecta a sí mismo. |
| **Cabeceras Faltantes** | Ausencia de `X-Content-Type-Options`, `X-Frame-Options` o `HSTS` sin vector de ataque comprobable. |
| **Email Spoofing / DNS** | Registros SPF `~all`, falta de DMARC o DNSSEC en dominios no transaccionales. |
| **Banners y Versiones** | Divulgación de números de versión de servidor (Apache, Nginx, PHP) sin PoC de un CVE explotable. |
| **Logout CSRF** | Forzar el cierre de sesión de un usuario no compromete confidencialidad ni integridad. |
| **Rate Limiting Trivial** | Falta de rate-limit en formularios públicos de contacto o endpoints que no consumen recursos críticos. |
| **Falsos Secretos** | API Keys públicas por diseño (Stripe `pk_live_...`, Google Maps API keys sin restricciones de cuota). |

---

## 3. Flujo de Ejecución Paso a Paso

### Paso 1: Contraste con `scope.txt`
Revisar minuciosamente la sección `## Fuera de Alcance` en `/workspace/engagements/<engagement>/scope.txt`.
- Si el subdominio, API o funcionalidad está explícitamente listado como fuera de alcance: **RECHAZAR INMEDIATAMENTE**.

### Paso 2: La Prueba del Impacto ("So What? Test")
El agente debe responder a tres preguntas obligatorias:
1. **¿Qué puede hacer el atacante que antes no podía hacer?** (e.g. Leer datos de otros usuarios, ejecutar comandos, alterar saldos).
2. **¿Requiere una interacción inverosímil de la víctima?** (e.g. Abrir 15 pestañas, desactivar protecciones del navegador).
3. **¿Cuál es la pérdida financiera, operativa o de reputación para la organización?**
Si la respuesta no demuestra una pérdida o riesgo claro: **DESCARTAR COMO INFORMATIVO O RUIDO**.

### Paso 3: Verificación de Duplicados en Divulgaciones Públicas
Para objetivos conocidos en plataformas públicas de Bug Bounty:
```bash
# Consultar si el mismo endpoint ya cuenta con reportes publicos en HackerOne
TARGET_HOST="target.example.com"
curl -s "https://hackerone.com/hacktivity.json?querystring=${TARGET_HOST}" | jq '.reports[] | {title: .title, url: .url, severity: .severity_rating}' 2>/dev/null || true
```

### Paso 4: Veredicto de la Compuerta
Emitir uno de dos dictámenes antes de permitir que la habilidad `report-generation` procese el hallazgo:

1. **APROBADO**:
   - Cumple con todas las reglas de scope.
   - Demuestra impacto verificable y reproducible.
   - Se autoriza su inclusión en `/workspace/engagements/<engagement>/REPORT.md`.
2. **DESCARTADO**:
   - Se documenta en el archivo interno `/workspace/engagements/<engagement>/out_of_scope_notes.md` con la justificación técnica de descarte, evitando perder tiempo del cliente.

---

## 4. Registro y Salida

Si un hallazgo es descartado por la compuerta:
```bash
pt-log mark "GUARD: Hallazgo descartado por política de alcance / falta de impacto de negocio (ver out_of_scope_notes.md)"
```
