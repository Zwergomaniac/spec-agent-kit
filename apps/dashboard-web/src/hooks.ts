import { useCallback, useEffect, useRef, useState } from 'react'

export const POLL_INTERVAL_MS = 10_000

export interface Polled<T> {
  data: T | null
  error: Error | null
  /** Zeitpunkt der letzten erfolgreichen Aktualisierung (ms). */
  updatedAt: number | null
  loading: boolean
  refresh: () => void
}

/**
 * Lädt Daten und aktualisiert sie alle 10 s, solange der Tab sichtbar ist (Spec 007 FR-010).
 * Beim Sichtbarwerden wird sofort neu geladen. Bei Fehlern bleiben die letzten Daten stehen.
 * Ein Wechsel von `key` verwirft die alten Daten.
 */
export function usePolled<T>(load: () => Promise<T>, key: string, intervalMs: number = POLL_INTERVAL_MS): Polled<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const loadRef = useRef(load)
  loadRef.current = load
  const generation = useRef(0)

  const run = useCallback(async (gen: number) => {
    try {
      const result = await loadRef.current()
      if (gen !== generation.current) return
      setData(result)
      setError(null)
      setUpdatedAt(Date.now())
    } catch (err) {
      if (gen !== generation.current) return
      setError(err instanceof Error ? err : new Error(String(err)))
    } finally {
      if (gen === generation.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    generation.current += 1
    const gen = generation.current
    setData(null)
    setError(null)
    setUpdatedAt(null)
    setLoading(true)
    void run(gen)

    const tick = (): void => {
      if (document.visibilityState === 'visible') void run(gen)
    }
    const timer = window.setInterval(tick, intervalMs)
    const onVisible = (): void => {
      if (document.visibilityState === 'visible') void run(gen)
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      generation.current += 1
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [key, intervalMs, run])

  const refresh = useCallback(() => {
    void run(generation.current)
  }, [run])

  return { data, error, updatedAt, loading, refresh }
}
