/**
 * Global theme composable that manages dark/light/system mode.
 * Persists preference to localStorage and reacts to system changes.
 */

type ThemePref = 'light' | 'dark' | 'system'

const themePref = ref<ThemePref>('system')
const isDark = ref(false)

let mediaQuery: MediaQueryList | null = null
let mediaHandler: ((e: MediaQueryListEvent) => void) | null = null
let initialized = false

function applyClass(dark: boolean) {
  if (import.meta.server) return
  isDark.value = dark
  if (dark) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

function resolveSystemDark(): boolean {
  if (import.meta.server) return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function applyTheme() {
  if (themePref.value === 'dark') {
    applyClass(true)
  } else if (themePref.value === 'light') {
    applyClass(false)
  } else {
    applyClass(resolveSystemDark())
  }
}

function persist(val: ThemePref) {
  if (import.meta.server) return
  try {
    localStorage.setItem('omnisell-theme', val)
  } catch {}
}

function restore(): ThemePref {
  if (import.meta.server) return 'system'
  try {
    const stored = localStorage.getItem('omnisell-theme')
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored
    }
  } catch {}
  return 'system'
}

export function useTheme() {
  if (!initialized && !import.meta.server) {
    initialized = true
    themePref.value = restore()
    applyTheme()

    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    mediaHandler = () => {
      if (themePref.value === 'system') {
        applyClass(resolveSystemDark())
      }
    }
    mediaQuery.addEventListener('change', mediaHandler)
  }

  const setTheme = (val: ThemePref) => {
    themePref.value = val
    persist(val)
    applyTheme()
  }

  return {
    themePref: readonly(themePref),
    isDark: readonly(isDark),
    setTheme,
  }
}
