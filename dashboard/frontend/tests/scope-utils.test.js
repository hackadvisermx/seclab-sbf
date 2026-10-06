import assert from 'node:assert/strict'
import { test } from 'node:test'

const { splitIpsAndCidrs } = await import('../src/scope-utils.js')

// Fase 105 / backlog A1: el editor de alcance guardaba cualquier CIDR
// escrito en el campo combinado "IPs y CIDRs" dentro de `ips`, lo que
// scripts/seclab_scope.py rechaza (ips exige ipaddress.ip_address()).

test('clasifica IPs sueltas en `ips` y deja `cidrs` vacio', () => {
  const { ips, cidrs } = splitIpsAndCidrs('192.168.1.10\n10.0.0.5')
  assert.deepEqual(ips, ['192.168.1.10', '10.0.0.5'])
  assert.deepEqual(cidrs, [])
})

test('clasifica rangos CIDR en `cidrs` y no en `ips`', () => {
  const { ips, cidrs } = splitIpsAndCidrs('10.0.0.0/24\n192.168.0.0/16')
  assert.deepEqual(cidrs, ['10.0.0.0/24', '192.168.0.0/16'])
  assert.deepEqual(ips, [])
})

test('separa correctamente una lista mixta de IPs y CIDRs', () => {
  const { ips, cidrs } = splitIpsAndCidrs('192.168.1.10\n10.0.0.0/24\n172.16.5.1')
  assert.deepEqual(ips, ['192.168.1.10', '172.16.5.1'])
  assert.deepEqual(cidrs, ['10.0.0.0/24'])
})

test('ignora lineas vacias, espacios y recorta cada valor', () => {
  const { ips, cidrs } = splitIpsAndCidrs('  192.168.1.10  \n\n   \n10.0.0.0/24\n')
  assert.deepEqual(ips, ['192.168.1.10'])
  assert.deepEqual(cidrs, ['10.0.0.0/24'])
})

test('texto vacio o indefinido devuelve ambas listas vacias', () => {
  assert.deepEqual(splitIpsAndCidrs(''), { ips: [], cidrs: [] })
  assert.deepEqual(splitIpsAndCidrs(undefined), { ips: [], cidrs: [] })
})
