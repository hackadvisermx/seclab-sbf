// Utilidades del editor de alcance (pestaña "Alcance" de EngagementDetailView.vue).
//
// El formulario combina IPs y CIDRs en un solo textarea ("IPs y CIDRs
// autorizados"), pero target.yaml los guarda en listas separadas: `ips`
// exige una direccion IP exacta (ipaddress.ip_address en
// scripts/seclab_scope.py) y `cidrs` exige una notacion de red
// (ipaddress.ip_network). Un CIDR guardado dentro de `ips` deja
// target.yaml invalido y rompe pt-scope y el pipeline de reconocimiento
// en el siguiente intento (fase 105 del backlog de mejoras, accion A1).

/**
 * Divide el texto del textarea combinado en sus dos listas: cualquier
 * linea con "/" (p. ej. 10.0.0.0/24) se clasifica como CIDR; el resto se
 * trata como IP individual. Lineas vacias o solo espacios se ignoran.
 *
 * @param {string} text
 * @returns {{ ips: string[], cidrs: string[] }}
 */
export function splitIpsAndCidrs(text) {
  const ips = []
  const cidrs = []
  for (const line of String(text ?? '').split('\n').map(s => s.trim()).filter(Boolean)) {
    if (line.includes('/')) {
      cidrs.push(line)
    } else {
      ips.push(line)
    }
  }
  return { ips, cidrs }
}
