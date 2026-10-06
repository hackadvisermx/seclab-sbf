// Utilidades de la tabla de resultados del sondeo (pestaña "Reconocimiento"
// de EngagementDetailView.vue).
//
// El backend expone en GET /api/v1/recon/{id}/status un campo
// `probe_results`: el contenido ya parseado de recon/probe_observations.jsonl,
// una fila por intento host+esquema que escribe seclab_recon_probe.py.
// Antes de esta fase (backlog A13) la unica forma de verla era descargar ese
// .jsonl crudo desde la pestaña Artefactos. El sondeo no lee el cuerpo de la
// respuesta (ver seclab_recon_probe.py), asi que no existe un "titulo" de
// pagina que mostrar; la tabla usa exactamente los campos que el pipeline
// captura hoy: host, esquema, direccion IP resuelta, codigo HTTP, estado del
// intento y, si aplica, el motivo de bloqueo o el destino de redireccion.

/**
 * Normaliza una fila cruda de probe_observations.jsonl a la forma que usa
 * la tabla. Las filas de hosts bloqueados o con error de DNS no tienen
 * `url`/`address`/`http_status`; quedan como null.
 *
 * @param {object} row
 * @returns {{host: string, scheme: string|null, address: string|null, httpStatus: number|null, status: string, detail: string|null}}
 */
export function normalizeProbeRow(row) {
  const url = row?.url || null
  const schemeMatch = url ? /^([a-z][a-z0-9+.-]*):\/\//i.exec(url) : null
  return {
    host: row?.host || '',
    scheme: schemeMatch ? schemeMatch[1].toLowerCase() : null,
    address: row?.address || null,
    httpStatus: typeof row?.http_status === 'number' ? row.http_status : null,
    status: row?.status || '',
    detail: row?.location || row?.reason || null,
  }
}

/**
 * @param {object[]} rows
 * @returns {ReturnType<typeof normalizeProbeRow>[]}
 */
export function normalizeProbeResults(rows) {
  return Array.isArray(rows) ? rows.map(normalizeProbeRow) : []
}

const NUMERIC_KEYS = new Set(['httpStatus'])

function compareValues(a, b, key) {
  if (NUMERIC_KEYS.has(key)) {
    const left = a[key] ?? -1
    const right = b[key] ?? -1
    return left - right
  }
  const left = String(a[key] ?? '')
  const right = String(b[key] ?? '')
  return left.localeCompare(right)
}

/**
 * Ordena filas ya normalizadas por una columna. No muta el arreglo recibido.
 *
 * @param {ReturnType<typeof normalizeProbeRow>[]} rows
 * @param {'host'|'scheme'|'address'|'httpStatus'|'status'} key
 * @param {'asc'|'desc'} direction
 */
export function sortProbeResults(rows, key, direction = 'asc') {
  const sorted = [...rows].sort((a, b) => compareValues(a, b, key))
  return direction === 'desc' ? sorted.reverse() : sorted
}
