# Reporte de Auditoría / Reto: [Nombre del Objetivo]

- **Fecha:** YYYY-MM-DD
- **Plataforma / Entorno:** [HackTheBox | TryHackMe | Cliente]
- **Auditor / Tester:** tester
- **Estado:** [En curso | Completado | En remediación]

---

## 1. Resumen Ejecutivo

_Resumen conciso (2 a 3 párrafos): qué objetivo fue evaluado, cuál fue el nivel de compromiso alcanzado y cuál fue la causa raíz principal del fallo de seguridad._

---

## 2. Alcance y Metodología

- **Objetivos analizados:**
- **Perfil de conexión:**
- **Metodología aplicada:** (PTES, OWASP Top 10, OSSTMM)

---

## 3. Matriz de Hallazgos

| # | Vulnerabilidad / Hallazgo | Severidad | Afectación | Estado |
|---|---|---|---|---|
| 1 | Inyección SQL en endpoint de login | Crítica | Confidencialidad / Integridad | Confirmado |
| 2 | Ejecución Remota de Código (RCE) vía upload | Crítica | Control total del servidor | Confirmado |
| 3 | Contraseñas débiles en servicio SSH | Alta | Acceso inicial no autorizado | Confirmado |
| 4 | Divulgación de información en cabeceras | Baja | Exposición de versiones | Confirmado |

---

## 4. Cadena de Compromiso Técnica

### 4.1 Reconocimiento y Enumeración
_Puertos abiertos, tecnologías detectadas, salidas relevantes de herramientas (nmap, ffuf, etc.)._

```bash
# Evidencia de comandos ejecutados
```

### 4.2 Análisis de Vulnerabilidades
_Hipótesis y validación de vectores identificados._

### 4.3 Explotación y Acceso Inicial
_Pasos detallados, ordenados y reproducibles para obtener el acceso inicial._

### 4.4 Post-Explotación y Escalada de Privilegios
_Enumeración local, vectores de elevación de privilegios a root/SYSTEM, movimiento lateral si aplica._

---

## 5. Evidencias Clave (Loot)

- **Capturas:** Ver directorio `screenshots/`
- **Archivos obtenidos / Flags:**
  ```text
  user: [flag o hash]
  root: [flag o hash]
  ```

---

## 6. Recomendaciones de Remediación

1. **Corto plazo (Mitigación inmediata):**
   - Acciones urgentes para cerrar vectores críticos expuestos.
2. **Mediano / Largo plazo (Remediación estructural):**
   - Corrección en el ciclo de desarrollo (SDLC), segmentación de red y políticas de mínimo privilegio.

---

## 7. Registro de Limpieza (Post-Engagement)

- [ ] Webshells o binarios transferidos retirados.
- [ ] Cuentas o claves SSH temporales eliminadas.
- [ ] Servicios o configuraciones restaurados a su estado original.

---

## 8. Callejones sin Salida y Lecciones Aprendidas

_Registro de caminos probados que no funcionaron (ayuda a evitar repetir trabajo y documenta defensas efectivas del objetivo)._
