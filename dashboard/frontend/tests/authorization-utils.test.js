import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFile } from 'node:fs/promises'
import { authorizationToForm, authorizationFromForm } from '../src/authorization-utils.js'

test('sin declaración todos los permisos permanecen desactivados', () => {
  assert.deepEqual(authorizationToForm(), {
    reference: '', valid_from: '', valid_until: '', allow_passive: false, allow_active: false,
  })
  assert.equal(authorizationToForm({ allow_active: 'false' }).allow_active, false)
})

test('fechas UTC y offset conservan el instante al editar en zona local', () => {
  for (const start of ['2026-10-08T00:00:00.123Z', '2026-10-07T18:00:00.123-06:00']) {
    const original = { reference: ' Permiso de fixture ', valid_from: start,
      valid_until: '2026-10-08T04:00:00.456Z', allow_passive: true, allow_active: false }
    const saved = authorizationFromForm(authorizationToForm(original))
    assert.equal(saved.valid_from, new Date(start).toISOString())
    assert.equal(saved.valid_until, original.valid_until)
    assert.equal(saved.reference, 'Permiso de fixture')
    assert.equal(saved.allow_active, false)
    assert.equal(saved.allow_passive, true)
  }
})

test('no se inventan fechas al faltar vigencia y las fechas inválidas fallan', () => {
  assert.equal(authorizationFromForm(authorizationToForm()).valid_until, '')
  assert.throws(() => authorizationFromForm({ reference: 'fixture', valid_from: 'invalid' }), /fecha inválida/)
})

test('el editor guarda declaración explícita con vigencia y permisos separados', async () => {
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  for (const field of ['reference', 'valid_from', 'valid_until', 'allow_passive', 'allow_active']) {
    assert.ok(source.includes(`v-model="authorizationForm.${field}"`))
  }
  assert.match(source, /authorization: authorizationFromForm\(authorizationForm.value\)/)
  assert.match(source, /no determina su validez legal/)
  assert.match(source, /terminal libre no está interceptada/)
})
