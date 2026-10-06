import assert from 'node:assert/strict'
import { test, beforeEach } from 'node:test'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!DOCTYPE html><html class="dark"><body></body></html>', {
  url: 'http://localhost',
})

globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.localStorage = dom.window.localStorage

const { initTheme, applyTheme, toggleTheme, useTheme } = await import('../src/theme.js')

beforeEach(() => {
  localStorage.clear()
  document.documentElement.className = 'dark'
})

test('initTheme establece dark por defecto si no hay preferencia en localStorage', () => {
  initTheme()
  assert.equal(document.documentElement.classList.contains('dark'), true)
  assert.equal(document.documentElement.classList.contains('light'), false)
})

test('initTheme respeta preferencia light en localStorage', () => {
  localStorage.setItem('seclab_theme', 'light')
  initTheme()
  assert.equal(document.documentElement.classList.contains('light'), true)
  assert.equal(document.documentElement.classList.contains('dark'), false)
})

test('toggleTheme conmuta fluidamente entre dark y light y persiste en localStorage', () => {
  applyTheme('dark')
  assert.equal(document.documentElement.classList.contains('dark'), true)

  const next = toggleTheme()
  assert.equal(next, 'light')
  assert.equal(document.documentElement.classList.contains('light'), true)
  assert.equal(document.documentElement.classList.contains('dark'), false)
  assert.equal(localStorage.getItem('seclab_theme'), 'light')

  const back = toggleTheme()
  assert.equal(back, 'dark')
  assert.equal(document.documentElement.classList.contains('dark'), true)
  assert.equal(document.documentElement.classList.contains('light'), false)
  assert.equal(localStorage.getItem('seclab_theme'), 'dark')
})

test('useTheme expone estado reactivo sincronizado', () => {
  const { theme } = useTheme()
  applyTheme('light')
  assert.equal(theme.value, 'light')
  applyTheme('dark')
  assert.equal(theme.value, 'dark')
})
