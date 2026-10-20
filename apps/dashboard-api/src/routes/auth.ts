import { Hono } from 'hono'
import { deleteCookie, getCookie, setCookie } from 'hono/cookie'
import { z } from 'zod'
import type { AppDeps } from '../app.js'
import { verifyPassword } from '../auth/password.js'
import { LoginGuard } from '../auth/rate-limit.js'
import { SESSION_COOKIE, SESSION_TTL_S, createSessionToken, verifySessionToken } from '../auth/session.js'
import { clientIp } from '../http.js'

const loginBody = z.object({ password: z.string().min(1).max(1024) }).strict()

export function authRoutes(deps: AppDeps): Hono {
  const app = new Hono()
  const guard = new LoginGuard(deps.db)

  app.post('/login', async (c) => {
    const ip = clientIp(c, deps.env.trustProxy)
    const wait = guard.lockedForSeconds(ip, deps.now())
    if (wait > 0) {
      c.header('Retry-After', String(wait))
      return c.json({ error: 'too_many_attempts', retry_after_s: wait }, 429)
    }

    let raw: unknown
    try {
      raw = await c.req.json()
    } catch {
      return c.json({ error: 'invalid_request' }, 400)
    }
    const body = loginBody.safeParse(raw)
    if (!body.success) return c.json({ error: 'invalid_request' }, 400)

    // Den Versuch vorab als Fehlversuch zählen: parallele Anfragen können die Sperre so nicht
    // unterlaufen, solange scrypt noch läuft. Bei Erfolg werden die Einträge der IP gelöscht.
    guard.recordFailure(ip, deps.now())
    const ok = await verifyPassword(body.data.password, deps.env.adminPasswordHash)
    if (!ok) return c.json({ error: 'invalid_credentials' }, 401)
    guard.clear(ip)
    setCookie(c, SESSION_COOKIE, createSessionToken(deps.env.sessionSecret, deps.now()), {
      httpOnly: true,
      secure: deps.env.secureCookie,
      sameSite: 'Strict',
      path: '/',
      maxAge: SESSION_TTL_S
    })
    return c.json({ ok: true })
  })

  app.post('/logout', (c) => {
    deleteCookie(c, SESSION_COOKIE, { path: '/', secure: deps.env.secureCookie })
    return c.json({ ok: true })
  })

  app.get('/me', (c) => {
    if (!verifySessionToken(getCookie(c, SESSION_COOKIE), deps.env.sessionSecret, deps.now())) {
      return c.json({ error: 'unauthorized' }, 401)
    }
    return c.json({ authenticated: true })
  })

  return app
}
