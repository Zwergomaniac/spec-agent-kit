import { useCallback, useEffect, useState } from 'react'

export type ThemeMode = 'system' | 'light' | 'dark'
const KEY = 'sak-theme'

function readStored(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'light' || v === 'dark' || v === 'system') return v
  } catch {
    // Speicher gesperrt: Systemvorgabe.
  }
  return 'system'
}

function systemPrefersDark(): boolean {
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function applyTheme(mode: ThemeMode): void {
  const dark = mode === 'dark' || (mode === 'system' && systemPrefersDark())
  document.documentElement.classList.toggle('dark', dark)
}

/** Dark Mode: System plus Umschalter (FR-011). Reihenfolge des Umschalters: System, Hell, Dunkel. */
export function useTheme(): { mode: ThemeMode; cycle: () => void } {
  const [mode, setMode] = useState<ThemeMode>(readStored)

  useEffect(() => {
    applyTheme(mode)
    if (mode !== 'system' || typeof window.matchMedia !== 'function') return
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (): void => applyTheme('system')
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [mode])

  const cycle = useCallback(() => {
    setMode((current) => {
      const next: ThemeMode = current === 'system' ? 'light' : current === 'light' ? 'dark' : 'system'
      try {
        localStorage.setItem(KEY, next)
      } catch {
        // egal
      }
      return next
    })
  }, [])

  return { mode, cycle }
}
