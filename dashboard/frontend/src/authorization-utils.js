export function authorizationToForm(value = {}) {
  const local = (raw) => {
    if (!raw) return ''
    const date = new Date(raw)
    if (!Number.isFinite(date.getTime())) return ''
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, -1)
  }
  return {
    reference: value.reference || '',
    valid_from: local(value.valid_from),
    valid_until: local(value.valid_until),
    allow_passive: value.allow_passive === true,
    allow_active: value.allow_active === true,
  }
}

export function authorizationFromForm(value) {
  const iso = (raw) => {
    if (!raw) return ''
    const date = new Date(raw)
    if (!Number.isFinite(date.getTime())) throw new Error('La vigencia contiene una fecha inválida.')
    return date.toISOString()
  }
  return {
    reference: value.reference.trim(),
    valid_from: iso(value.valid_from),
    valid_until: iso(value.valid_until),
    allow_passive: value.allow_passive === true,
    allow_active: value.allow_active === true,
  }
}
