import { ref } from 'vue'

const currentTheme = ref('dark')

export function initTheme() {
  if (typeof window === 'undefined') return
  const saved = localStorage.getItem('seclab_theme')
  if (saved === 'light') {
    applyTheme('light')
  } else {
    applyTheme('dark')
  }
}

export function applyTheme(theme) {
  currentTheme.value = theme
  if (typeof document !== 'undefined') {
    if (theme === 'light') {
      document.documentElement.classList.remove('dark')
      document.documentElement.classList.add('light')
    } else {
      document.documentElement.classList.remove('light')
      document.documentElement.classList.add('dark')
    }
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('seclab_theme', theme)
  }
}

export function toggleTheme() {
  const next = currentTheme.value === 'dark' ? 'light' : 'dark'
  applyTheme(next)
  return next
}

export function useTheme() {
  return {
    theme: currentTheme,
    toggleTheme,
    applyTheme,
  }
}
