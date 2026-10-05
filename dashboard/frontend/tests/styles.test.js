import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'
import postcss from 'postcss'
import tailwind from '@tailwindcss/postcss'

const source = fileURLToPath(new URL('../src/style.css', import.meta.url))
const result = await postcss([tailwind()]).process(await readFile(source, 'utf8'), { from: source })
const rules = new Map()
result.root.walkRules(rule => rules.set(rule.selector, rule))

function declaration(selector, property) {
  let value
  rules.get(selector)?.walkDecls(property, entry => { value = entry.value })
  assert.ok(value, `${selector}: falta ${property}`)
  return value
}

test('compila la tarjeta táctica y conserva la paleta y tipografía configuradas', () => {
  assert.equal(declaration('.tactical-card', 'background-color'), '#0d1322')
  assert.equal(declaration('.tactical-card', 'border-color'), '#1b253b')
  assert.match(declaration('.tactical-card', 'padding'), /5/)
  assert.match(declaration('.font-mono', 'font-family'), /JetBrains Mono/)
  assert.equal(declaration('body', 'background-color'), '#070b14')
  assert.equal(result.css.includes('@apply'), false)
})

test('genera variantes responsive, foco accesible, impresión y utilidades de formularios', () => {
  assert.ok(rules.has('.lg\\:grid-cols-3'))
  assert.ok(rules.has('.focus\\:outline-hidden:focus'))
  assert.ok(rules.has('.print\\:bg-white'))
  assert.ok(rules.has('.disabled\\:opacity-50:disabled'))
  assert.ok(rules.has('.bg-linear-to-r'))
  assert.match(declaration('.rounded-sm', 'border-radius'), /radius-sm/)
  assert.match(declaration('.shadow-xs', '--tw-shadow'), /0 1px 2px/)
})
