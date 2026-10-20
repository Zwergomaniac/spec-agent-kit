import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { createTestCtx, type TestCtx } from './helpers.js'

describe('Statische UI mit SPA-Fallback (T019)', () => {
  let ctx: TestCtx

  beforeAll(async () => {
    const root = mkdtempSync(join(tmpdir(), 'sak-web-'))
    mkdirSync(join(root, 'assets'))
    writeFileSync(join(root, 'index.html'), '<!doctype html><title>UI</title>')
    writeFileSync(join(root, 'assets', 'app-abc.js'), 'console.log(1)')
    writeFileSync(join(tmpdir(), 'sak-secret.txt'), 'geheim')
    ctx = await createTestCtx({ webDist: root })
  })

  it('liefert index.html unter / und für unbekannte Pfade ohne Endung', async () => {
    for (const path of ['/', '/project/immo-agent', '/run/a/b']) {
      const res = await ctx.request(path)
      expect(res.status, path).toBe(200)
      expect(res.headers.get('content-type')).toContain('text/html')
      expect(res.headers.get('cache-control')).toBe('no-cache')
      expect(await res.text()).toContain('<title>UI</title>')
    }
  })

  it('liefert Assets mit langem Cache und korrektem Typ', async () => {
    const res = await ctx.request('/assets/app-abc.js')
    expect(res.status).toBe(200)
    expect(res.headers.get('content-type')).toContain('javascript')
    expect(res.headers.get('cache-control')).toContain('immutable')
  })

  it('antwortet auf fehlende Dateien mit 404 statt index.html', async () => {
    expect((await ctx.request('/assets/fehlt.js')).status).toBe(404)
  })

  it('unbekannte API-Pfade bleiben JSON-404', async () => {
    const res = await ctx.request('/api/gibt-es-nicht')
    expect(res.status).toBe(404)
    expect(await res.json()).toEqual({ error: 'not_found' })
  })

  it('verlässt das Web-Verzeichnis nie (Path Traversal)', async () => {
    const res = await ctx.request('/..%2fsak-secret.txt')
    expect(await res.text()).not.toContain('geheim')
    expect((await ctx.request('/%2e%2e/sak-secret.txt')).status).not.toBe(200)
  })

  it('healthz bleibt erreichbar', async () => {
    expect((await ctx.request('/healthz')).status).toBe(200)
  })
})
