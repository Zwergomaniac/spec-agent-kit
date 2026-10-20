import { describe, expect, it } from 'vitest'
import { EnvError, loadEnv } from '../src/env.js'
import { hashPassword, verifyPassword } from '../src/auth/password.js'
import { createSessionToken, verifySessionToken } from '../src/auth/session.js'
import { ADMIN_PASSWORD, SESSION_SECRET, createTestCtx } from './helpers.js'

const login = (ctx: Awaited<ReturnType<typeof createTestCtx>>, password: string, headers: Record<string, string> = {}) =>
  ctx.request('/api/auth/login', {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...headers },
    body: JSON.stringify({ password })
  })

describe('Passwort und Session', () => {
  it('hasht mit scrypt und prüft in konstanter Zeit', async () => {
    const hash = await hashPassword('ein-langes-passwort')
    expect(hash).toMatch(/^scrypt:\d+:\d+:\d+:[\w-]+:[\w-]+$/)
    expect(hash).not.toContain('$')
    expect(await verifyPassword('ein-langes-passwort', hash)).toBe(true)
    expect(await verifyPassword('falsch', hash)).toBe(false)
    expect(await verifyPassword('x', 'kaputt')).toBe(false)
  })

  it('signierte Tokens: gültig, manipuliert, abgelaufen, falsches Secret', () => {
    const t0 = Date.parse('2026-10-20T00:00:00Z')
    const token = createSessionToken(SESSION_SECRET, t0)
    expect(verifySessionToken(token, SESSION_SECRET, t0 + 1000)).toBe(true)
    expect(verifySessionToken(token, 'anderes-secret-anderes-secret-12345', t0)).toBe(false)
    expect(verifySessionToken(`${token}x`, SESSION_SECRET, t0)).toBe(false)
    expect(verifySessionToken(undefined, SESSION_SECRET, t0)).toBe(false)
    expect(verifySessionToken(token, SESSION_SECRET, t0 + 12 * 3600 * 1000 + 1000)).toBe(false)
  })
})

describe('Umgebung', () => {
  it('verweigert den Start ohne Pflicht-Secrets mit klarer Meldung', () => {
    expect(() => loadEnv({})).toThrow(EnvError)
    try {
      loadEnv({})
    } catch (err) {
      expect((err as Error).message).toContain('SAK_ADMIN_PASSWORD_HASH')
      expect((err as Error).message).toContain('SAK_SESSION_SECRET')
    }
  })

  it('verlangt ein ausreichend langes Session-Secret und setzt Defaults', async () => {
    const hash = 'scrypt:1:1:1:aaaa:bbbb'
    expect(() => loadEnv({ SAK_ADMIN_PASSWORD_HASH: hash, SAK_SESSION_SECRET: 'kurz' })).toThrow(/zu kurz/)
    const env = loadEnv({ SAK_ADMIN_PASSWORD_HASH: hash, SAK_SESSION_SECRET: SESSION_SECRET })
    expect(env).toMatchObject({ port: 3000, dbPath: '/data/dashboard.db', retentionDays: 30, trustProxy: true, secureCookie: true })
    expect(loadEnv({ SAK_ADMIN_PASSWORD_HASH: hash, SAK_SESSION_SECRET: SESSION_SECRET, NODE_ENV: 'development' }).secureCookie).toBe(false)
  })
})

describe('Login-Routen', () => {
  it('setzt ein HttpOnly-, Secure-, SameSite=Strict-Cookie mit 12 h Laufzeit', async () => {
    const ctx = await createTestCtx()
    const res = await login(ctx, ADMIN_PASSWORD)
    expect(res.status).toBe(200)
    const cookie = res.headers.get('set-cookie') ?? ''
    expect(cookie).toMatch(/^sak_session=/)
    expect(cookie).toMatch(/HttpOnly/i)
    expect(cookie).toMatch(/Secure/i)
    expect(cookie).toMatch(/SameSite=Strict/i)
    expect(cookie).toMatch(/Max-Age=43200/)
  })

  it('weist ein falsches Passwort ab und liefert keine Session', async () => {
    const ctx = await createTestCtx()
    const res = await login(ctx, 'falsch')
    expect(res.status).toBe(401)
    expect(res.headers.get('set-cookie')).toBeNull()
  })

  it('sperrt eine IP für 15 min nach 5 Fehlversuchen, auch für das richtige Passwort', async () => {
    const ctx = await createTestCtx()
    const ip = { 'x-forwarded-for': '203.0.113.9' }
    for (let i = 0; i < 5; i += 1) expect((await login(ctx, 'falsch', ip)).status).toBe(401)
    const locked = await login(ctx, ADMIN_PASSWORD, ip)
    expect(locked.status).toBe(429)
    expect(Number(locked.headers.get('retry-after'))).toBeGreaterThan(0)
    // Eine andere IP ist nicht betroffen.
    expect((await login(ctx, ADMIN_PASSWORD, { 'x-forwarded-for': '203.0.113.10' })).status).toBe(200)
    // Nach 15 Minuten ist die Sperre vorbei.
    ctx.clock.now += 15 * 60 * 1000 + 1000
    expect((await login(ctx, ADMIN_PASSWORD, ip)).status).toBe(200)
  })

  it('ignoriert vom Client vorangestellte X-Forwarded-For-Einträge', async () => {
    const ctx = await createTestCtx()
    for (let i = 0; i < 5; i += 1) {
      await login(ctx, 'falsch', { 'x-forwarded-for': `10.0.0.${i}, 198.51.100.7` })
    }
    expect((await login(ctx, ADMIN_PASSWORD, { 'x-forwarded-for': '1.2.3.4, 198.51.100.7' })).status).toBe(429)
  })

  it('/api/auth/me und Logout', async () => {
    const ctx = await createTestCtx()
    expect((await ctx.request('/api/auth/me')).status).toBe(401)
    const cookie = await ctx.login()
    expect((await ctx.request('/api/auth/me', { cookie })).status).toBe(200)
    const out = await ctx.request('/api/auth/logout', { method: 'POST', cookie })
    expect(out.status).toBe(200)
    expect(out.headers.get('set-cookie')).toMatch(/Max-Age=0|Expires=/i)
  })
})

describe('Zugriffsschutz', () => {
  it('verlangt eine Session für alle API-Routen außer healthz, login und ingest', async () => {
    const ctx = await createTestCtx()
    ctx.addProject('proj-a')
    const paths = [
      ['GET', '/api/meta'],
      ['GET', '/api/portfolio'],
      ['GET', '/api/projects/proj-a'],
      ['GET', '/api/projects/proj-a/events'],
      ['GET', '/api/projects/proj-a/runs/088-20261019-101500'],
      ['GET', '/api/admin/projects'],
      ['POST', '/api/admin/projects'],
      ['POST', '/api/admin/projects/proj-a/rotate'],
      ['DELETE', '/api/admin/projects/proj-a']
    ] as const
    for (const [method, path] of paths) {
      const res = await ctx.request(path, { method })
      expect(res.status, `${method} ${path}`).toBe(401)
    }
    expect((await ctx.request('/healthz')).status).toBe(200)
  })

  it('weist manipulierte und abgelaufene Cookies ab', async () => {
    const ctx = await createTestCtx()
    const cookie = await ctx.login()
    expect((await ctx.request('/api/meta', { cookie })).status).toBe(200)
    expect((await ctx.request('/api/meta', { cookie: `${cookie}tampered` })).status).toBe(401)
    ctx.clock.now += 12 * 3600 * 1000 + 5000
    expect((await ctx.request('/api/meta', { cookie })).status).toBe(401)
  })

  it('weist Schreibzugriffe mit fremdem Origin ab', async () => {
    const ctx = await createTestCtx()
    const cookie = await ctx.login()
    const res = await ctx.request('http://dash.example/api/admin/projects', {
      method: 'POST',
      cookie,
      headers: { 'content-type': 'application/json', origin: 'https://evil.example', host: 'dash.example' },
      body: JSON.stringify({ key: 'x-evil', name: 'x' })
    })
    expect(res.status).toBe(403)
  })

  it('gibt bei internen Fehlern kein Stacktrace-Detail nach außen', async () => {
    const ctx = await createTestCtx()
    ctx.db.close()
    const res = await ctx.request('/healthz')
    expect(res.status).toBe(500)
    expect(await res.json()).toEqual({ error: 'internal_error' })
  })

  it('setzt Sicherheits-Header und verbietet Caching der API', async () => {
    const ctx = await createTestCtx()
    const res = await ctx.request('/healthz')
    expect(res.headers.get('content-security-policy')).toContain("default-src 'self'")
    expect(res.headers.get('x-content-type-options')).toBe('nosniff')
    const api = await ctx.request('/api/meta')
    expect(api.headers.get('cache-control')).toBe('no-store')
  })
})
