import { deepLinks, parseDeepLink, type DeepLinkRoute, type ProjectTab } from '@sak/contracts'
import { useEffect, useState } from 'react'

/** Deep-Link-Routen aus den Contracts plus die UI-eigenen Ansichten Login und Admin (Spec 007 FR-008). */
export type Route = DeepLinkRoute | { view: 'login'; next: string | null } | { view: 'admin' }

function isInternalHash(value: string | null): value is string {
  return value !== null && value.startsWith('#/') && !value.startsWith('#/login')
}

export function parseRoute(hash: string): Route {
  const clean = hash.replace(/^#/, '')
  const queryAt = clean.indexOf('?')
  const path = queryAt === -1 ? clean : clean.slice(0, queryAt)
  if (path === '/admin') return { view: 'admin' }
  if (path === '/login') {
    const next = new URLSearchParams(queryAt === -1 ? '' : clean.slice(queryAt + 1)).get('next')
    return { view: 'login', next: isInternalHash(next) ? next : null }
  }
  // Leer oder unbekannt: parseDeepLink liefert die Startansicht Portfolio.
  return parseDeepLink(hash)
}

export const links = {
  portfolio: deepLinks.portfolio,
  project: (key: string, tab?: ProjectTab) => deepLinks.project(key, tab),
  run: deepLinks.run,
  admin: () => '#/admin',
  login: (next?: string) => (next ? `#/login?next=${encodeURIComponent(next)}` : '#/login')
}

/** Wie `links.project`, aber ohne Exception bei Schlüsseln, die der Server liefert und die der Vertrag nicht kennt. */
export function safeLink(build: () => string, fallback: string = deepLinks.portfolio()): string {
  try {
    return build()
  } catch {
    return fallback
  }
}

export function navigate(hash: string): void {
  if (window.location.hash === hash) window.dispatchEvent(new HashChangeEvent('hashchange'))
  else window.location.hash = hash
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash))
  useEffect(() => {
    const onChange = (): void => setRoute(parseRoute(window.location.hash))
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}
