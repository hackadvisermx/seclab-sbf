---
name: business-logic-audit
description: Auditoría metodológica de flujos de negocio multi-paso, alteración de estados, parámetros de precio/cantidad y condiciones de carrera.
version: 1.0.0
author: hackadvisermx/seclab-sbf
license: MIT
category: logic
tools:
  - curl
  - jq
  - pt-log
  - view_file
---

# Skill: Business Logic & State Transition Audit (`business-logic-audit`)

## 1. Propósito y Alcance

Inspirada en la **Fase 03 de mdpsec/bug-bounty-hunting-prompts**, esta habilidad guía al agente en la identificación de fallas en la lógica de negocio, validaciones del lado del cliente y transiciones indebidas de estado en flujos críticos (e-commerce, pasarelas de pago, restablecimiento de contraseñas, canje de cupones).

Su objetivo es detectar de forma determinista:
- **Violación de Máquinas de Estado (Step Skipping)**: Avanzar directamente a la confirmación de una transacción sin haber completado los pasos previos de pago o verificación.
- **Manipulación de Parámetros Críticos**: Valores negativos en cantidades, precios arbitrarios enviados en el cuerpo JSON, o mezclas incompatibles de divisas.
- **Condiciones de Carrera (Race Conditions / TOCTOU)**: Ráfagas concurrentes de peticiones para canjear un cupón de un solo uso múltiples veces o duplicar retiros de saldo.

---

## 2. Precondiciones y Guardrails (Compuerta de Lógica de Negocio)

1. **Entorno Sandbox / Datos de Prueba**:
   - Toda prueba que involucre pagos, pedidos o transacciones DEBE utilizar pasarelas en modo de prueba (e.g. Stripe test keys, tarjetas 4242..., saldos virtuales).
   - **PROHIBIDO**: Comprometer transacciones comerciales reales o afectar inventarios de clientes en producción.
2. **Límite de Ráfaga en Condiciones de Carrera**:
   - Para verificar condiciones de carrera (Race Conditions), limitar las peticiones concurrentes a un máximo de **10 peticiones paralelas**.
   - No ejecutar bucles infinitos de fuerza bruta.
3. **Trazabilidad Continua**:
   - Todo flujo evaluado debe ser registrado mediante `pt-log`.

---

## 3. Flujo de Ejecución Paso a Paso

### Paso 1: Mapeo del Flujo de Estados
Documentar los pasos de la secuencia analizada:
```text
[Paso 1: Agregar al Carrito] -> [Paso 2: Dirección de Envío] -> [Paso 3: Pago y Autorización] -> [Paso 4: Confirmación del Pedido]
```

### Paso 2: Prueba de Salto de Estados (Step Skipping)
Intentar invocar el endpoint final (`Paso 4`) enviando únicamente los identificadores generados en `Paso 1` o `Paso 2`, sin invocar la pasarela de pago:

```bash
ENGAGEMENT="<nombre_engagement>"
EVIDENCE_DIR="/workspace/engagements/${ENGAGEMENT}/evidence"
mkdir -p "${EVIDENCE_DIR}"

ORDER_ID="ord_test_901"
TOKEN_USER="<jwt_usuario>"

# Invocar directamente la confirmacion sin pasar por pasarela de pago
curl -isk -X POST "https://target.example.com/api/v1/checkout/confirm" \
  -H "Authorization: Bearer ${TOKEN_USER}" \
  -H "Content-Type: application/json" \
  -d "{\"order_id\": \"${ORDER_ID}\", \"status\": \"paid\"}" \
  > "${EVIDENCE_DIR}/test_step_skipping.txt"
```

### Paso 3: Manipulación de Parámetros de Negocio (Negative Values & Rounding)
1. **Cantidades Negativas o Cero**:
   - Intentar agregar un producto con cantidad `-1` junto con otro con cantidad `1` para reducir el total del carrito a `0` o valor negativo.
2. **Parámetros Ocultos de Precio**:
   - Enviar `"price": 0.01` o `"discount": 100` en el cuerpo de la petición si el servidor confía indebidamente en los valores provistos por el cliente.

### Paso 4: Evaluación de Condiciones de Carrera (Race Conditions)
Comprobar si el backend valida y descuenta los recursos antes de confirmar la transacción sin locks en base de datos:

```bash
# Ejemplo: Canje simultaneo de un cupon de descuento de 1 solo uso
COUPON_CODE="PROMO2026"
TARGET_URL="https://target.example.com/api/v1/coupons/redeem"

# Ejecutar 10 peticiones concurrentes en paralelo usando curl en background
for i in {1..10}; do
  curl -s -X POST "${TARGET_URL}" \
    -H "Authorization: Bearer ${TOKEN_USER}" \
    -H "Content-Type: application/json" \
    -d "{\"coupon\": \"${COUPON_CODE}\"}" \
    -o "${EVIDENCE_DIR}/race_resp_${i}.json" &
done
wait

# Analizar cuantas peticiones obtuvieron exito (HTTP 200)
grep -l '"success":true' "${EVIDENCE_DIR}"/race_resp_*.json | wc -l
```

---

## 4. Registro y Salida

Si se confirma una debilidad de lógica de negocio o condición de carrera:
1. Estampar la marca en la bitácora:
   ```bash
   pt-log mark "VULN-LOGIC-01: Confirmada condición de carrera en canje de cupones (${TARGET_URL})"
   ```
2. Generar ficha estructurada en `${EVIDENCE_DIR}/VULN-LOGIC-01.md`:
   - Diagrama del flujo de negocio afectado.
   - Peticiones HTTP exactas y respuestas demostrando la inconsistencia de estado.
   - Severidad CVSS v3.1 / v4.0.
   - Recomendación técnica: Implementación de transacciones atómicas con bloqueo optimista/pesimista (`SELECT ... FOR UPDATE`), idempotencia mediante claves únicas y validación estricta de estados en el servidor.
