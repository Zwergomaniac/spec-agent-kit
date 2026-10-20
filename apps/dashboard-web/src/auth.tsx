import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, setUnauthorizedHandler } from './api'

type Status = 'checking' | 'authenticated' | 'anonymous'

interface AuthValue {
  status: Status
  login: (password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('checking')

  useEffect(() => {
    setUnauthorizedHandler(() => setStatus('anonymous'))
    let cancelled = false
    api
      .me()
      .then(() => !cancelled && setStatus('authenticated'))
      // 401 und Netzfehler führen gleichermaßen zur Anmeldung; ein Netzfehler zeigt sich beim Versuch.
      .catch(() => !cancelled && setStatus('anonymous'))
    return () => {
      cancelled = true
      setUnauthorizedHandler(null)
    }
  }, [])

  const login = useCallback(async (password: string) => {
    await api.login(password)
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } finally {
      setStatus('anonymous')
    }
  }, [])

  const value = useMemo(() => ({ status, login, logout }), [status, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth außerhalb von AuthProvider')
  return ctx
}
