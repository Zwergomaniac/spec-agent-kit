import type { Context, MiddlewareHandler } from 'hono'
import { getConnInfo } from '@hono/node-server/conninfo'
import { getCookie } from 'hono/cookie'
import { SESSION_COOKIE, verifySessionToken } from './auth/session.js'
import type { AppDeps } from './app.js'

/**
 * Client-IP für Sperren und Limits. Hinter dem vertrauenswürdigen Proxy (SAK_TRUST_PROXY) zählt der
 * letzte X-Forwarded-For-Eintrag, den der Proxy selbst angehängt hat; vom Client mitgeschickte
 * vordere Einträge werden ignoriert.
 */
export function clientIp(c: Context, trustProxy: boolean): string {
  if (trustProxy) {
    const forwarded = c.req.header('x-forwarded-for')
    const last = forwarded
      ?.split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .at(-1)
    if (last) return last
  }
  try {
    return getConnInfo(c).remote.address ?? 'unknown'
  } catch {
    return 'unknown'
  }
}

export function requireSession(deps: AppDeps): MiddlewareHandler {
  return async (c, next) => {
    const token = getCookie(c, SESSION_COOKIE)
    if (!verifySessionToken(token, deps.env.sessionSecret, deps.now())) {
      return c.json({ error: 'unauthorized' }, 401)
    }
    await next()
  }
}

/**
 * Schutz gegen Cross-Site-Schreibzugriffe zusätzlich zu SameSite=Strict: Trägt ein Request mit
 * Methode ungleich GET/HEAD einen Origin-Header, muss dessen Host zum Host des Requests passen.
 */
export function sameOriginForWrites(deps: AppDeps): MiddlewareHandler {
  return async (c, next) => {
    const method = c.req.method
    if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
      const origin = c.req.header('origin')
      if (origin) {
        const host = (deps.env.trustProxy ? c.req.header('x-forwarded-host') : undefined) ?? c.req.header('host')
        let originHost: string | null = null
        try {
          originHost = new URL(origin).host
        } catch {
          originHost = null
        }
        if (!originHost || originHost !== host) return c.json({ error: 'forbidden_origin' }, 403)
      }
    }
    await next()
  }
}
