import { vocabulary, type Board, type IngestResult, type SakEvent } from '@sak/contracts'
import { beforeEach, describe, expect, it } from 'vitest'
import { runRetention } from '../src/services/retention.js'
import { DASHBOARD_VERSION } from '../src/version.js'
import { createTestCtx, ingestRequest, makeEvent, pilotBoard, pilotEvents, type TestCtx } from './helpers.js'
import pkg from '../package.json' with { type: 'json' }

const RUN = '088-20261019-101500'

async function json<T>(res: Response): Promise<T> {
  return (await res.json()) as T
}

describe('Lese-API mit dem Pilot-Board', () => {
  let ctx: TestCtx
  let cookie: string

  beforeEach(async () => {
    ctx = await createTestCtx()
    cookie = await ctx.login()
    const token = ctx.addProject('immo-agent', 'ImmoAgent')
    ctx.addProject('leer', 'Leeres Projekt')
    const res = await ctx.ingestAs(token, ingestRequest('immo-agent', pilotEvents(), pilotBoard()))
    const result = (await res.json()) as IngestResult
    expect(result.board_accepted).toBe(true)
    expect(result.rejected).toEqual([])
  })

  it('GET /api/meta liefert Version, Vokabular und deutsche Labels', async () => {
    const body = await json<{ kit_version: string; vocabulary: typeof vocabulary.levels; labels: { verdict: Record<string, string> } }>(
      await ctx.request('/api/meta', { cookie })
    )
    expect(body.kit_version).toBe(DASHBOARD_VERSION)
    expect(DASHBOARD_VERSION).toBe(pkg.version)
    expect(body.vocabulary.stage).toEqual(vocabulary.levels.stage)
    expect(body.labels.verdict.needs_human).toBe('Mensch prüft')
  })

  it('GET /api/portfolio: eine Karte je Projekt mit korrekten Werten', async () => {
    const body = await json<{ projects: Array<Record<string, any>> }>(await ctx.request('/api/portfolio', { cookie }))
    expect(body.projects.map((p) => p.key)).toEqual(['immo-agent', 'leer'])

    const immo = body.projects[0]!
    expect(immo).toMatchObject({
      name: 'ImmoAgent',
      has_board: true,
      attention_count: 3,
      in_progress: 3,
      active_run: { run_id: RUN, spec: '088-kartenansicht', state: 'escalated', round: 2, max_rounds: 2 },
      escalation: { run_id: RUN, reason: 'Rundenlimit erreicht, offene Muss-Befunde' }
    })
    expect(immo.active_run.current_station).toMatchObject({ role: expect.any(String), agent: expect.any(String) })
    expect(immo.warnings).toContain('idle')
    expect(immo.warnings).not.toContain('no_push_24h')
    expect(immo.last_activity).not.toBeNull()

    const leer = body.projects[1]!
    expect(leer).toMatchObject({ has_board: false, active_run: null, escalation: null, attention_count: 0, in_progress: 0 })
  })

  it('GET /api/portfolio: Stationsverteilung, fertige Specs, Aufmerksamkeitsvorschau und letzter Marker', async () => {
    const body = await json<{ projects: Array<Record<string, any>> }>(await ctx.request('/api/portfolio', { cookie }))
    const immo = body.projects.find((p) => p.key === 'immo-agent')!
    const board = pilotBoard()

    // Alle Stationen des Vokabulars sind gesetzt; zurückgestellte Specs zählen nicht mit.
    expect(Object.keys(immo.stage_counts)).toEqual([...vocabulary.levels.stage])
    expect(immo.stage_counts).toEqual({ specified: 1, clarified: 1, planned: 1, tasked: 1, implementing: 3, implemented: 1, deployed: 1, verified: 2 })
    expect(Object.values(immo.stage_counts).reduce((a: number, b) => a + (b as number), 0)).toBe(board.specs.filter((s) => !s.descoped).length)

    expect(immo.done).toBe(board.metrics.done)
    expect(immo.attention_total).toBe(board.attention.length)
    expect(immo.attention_preview).toHaveLength(Math.min(3, board.attention.length))
    expect(immo.attention_preview[0]).toEqual({ kind: board.attention[0]!.kind, spec: board.attention[0]!.spec })
    expect(immo.last_marker).toMatchObject({ kind: 'deploy', specs: [66] })

    const leer = body.projects.find((p) => p.key === 'leer')!
    expect(leer).toMatchObject({ done: 0, attention_preview: [], attention_total: 0, last_marker: null })
    expect(Object.values(leer.stage_counts).every((n) => n === 0)).toBe(true)
  })

  it('Portfolio: Warnung no_push_24h erscheint nach 24 h ohne Einlieferung', async () => {
    ctx.clock.now += 25 * 3600 * 1000
    cookie = await ctx.login() // die alte Session ist nach 12 h abgelaufen
    const body = await json<{ projects: Array<{ key: string; warnings: string[] }> }>(await ctx.request('/api/portfolio', { cookie }))
    expect(body.projects.find((p) => p.key === 'immo-agent')!.warnings).toContain('no_push_24h')
    expect(body.projects.find((p) => p.key === 'leer')!.warnings).toContain('no_push_24h')
  })

  it('GET /api/projects/:key liefert Board und Ingest-Status', async () => {
    const body = await json<{ project: { key: string }; board: Board; ingest: { event_count: number; last_ingest_at: string } }>(
      await ctx.request('/api/projects/immo-agent', { cookie })
    )
    expect(body.board).toEqual(pilotBoard())
    expect(body.ingest.event_count).toBeGreaterThan(0)
    expect(body.ingest.last_ingest_at).toBeTruthy()

    const empty = await json<{ board: unknown }>(await ctx.request('/api/projects/leer', { cookie }))
    expect(empty.board).toBeNull()
    expect((await ctx.request('/api/projects/gibt-es-nicht', { cookie })).status).toBe(404)
    expect((await ctx.request('/api/projects/UNGÜLTIG!', { cookie })).status).toBe(404)
  })

  it('GET /api/projects/:key/runs/:runId: Lauf aus dem Board plus Events', async () => {
    const body = await json<{ run: { run_id: string; stations: unknown[] }; events: SakEvent[] }>(
      await ctx.request(`/api/projects/immo-agent/runs/${RUN}`, { cookie })
    )
    expect(body.run.run_id).toBe(RUN)
    expect(body.run.stations).toHaveLength(5)
    expect(body.events.length).toBeGreaterThan(0)
    expect(body.events.every((e) => e.run_id === RUN)).toBe(true)
    const ts = body.events.map((e) => Date.parse(e.ts))
    expect([...ts].sort((a, b) => a - b)).toEqual(ts)

    expect((await ctx.request('/api/projects/immo-agent/runs/999-20200101-000000', { cookie })).status).toBe(404)
    expect((await ctx.request('/api/projects/immo-agent/runs/kaputt', { cookie })).status).toBe(404)
  })

  it('GET /api/projects/:key/events: Filter run, since, limit (max 500)', async () => {
    const all = await json<{ events: SakEvent[] }>(await ctx.request('/api/projects/immo-agent/events?limit=500', { cookie }))
    expect(all.events.length).toBeGreaterThan(2)

    const limited = await json<{ events: SakEvent[] }>(await ctx.request('/api/projects/immo-agent/events?limit=2', { cookie }))
    expect(limited.events).toHaveLength(2)
    // Ohne since: die neuesten Events, aufsteigend.
    expect(limited.events.map((e) => e.event_id)).toEqual(all.events.slice(-2).map((e) => e.event_id))

    const first = all.events[0]!
    const since = encodeURIComponent(first.ts)
    const after = await json<{ events: SakEvent[] }>(await ctx.request(`/api/projects/immo-agent/events?since=${since}&limit=500`, { cookie }))
    expect(after.events.every((e) => Date.parse(e.ts) > Date.parse(first.ts))).toBe(true)

    const byRun = await json<{ events: SakEvent[] }>(await ctx.request(`/api/projects/immo-agent/events?run=${RUN}`, { cookie }))
    expect(byRun.events.every((e) => e.run_id === RUN)).toBe(true)

    expect((await ctx.request('/api/projects/immo-agent/events?limit=501', { cookie })).status).toBe(400)
    expect((await ctx.request('/api/projects/immo-agent/events?limit=0', { cookie })).status).toBe(400)
    expect((await ctx.request('/api/projects/immo-agent/events?since=gestern', { cookie })).status).toBe(400)
    expect((await ctx.request('/api/projects/immo-agent/events?run=x', { cookie })).status).toBe(400)
  })

  it('zeigt zwei eingelieferte Projekte als zwei Karten (US1)', async () => {
    const tokenB = ctx.addProject('zweites')
    const board: Board = { ...pilotBoard(), project: { key: 'zweites', name: 'Zweites', base_branch: 'main' }, runs: [], attention: [] }
    await ctx.ingestAs(tokenB, ingestRequest('zweites', [makeEvent('zweites')], board))
    const body = await json<{ projects: Array<{ key: string; escalation: unknown; active_run: unknown }> }>(
      await ctx.request('/api/portfolio', { cookie })
    )
    expect(body.projects.filter((p) => p.key !== 'leer')).toHaveLength(2)
    expect(body.projects.find((p) => p.key === 'zweites')).toMatchObject({ escalation: null, active_run: null })
  })
})

describe('Admin und Retention', () => {
  it('legt Projekte an (Schlüssel einmalig), erneuert und entfernt sie', async () => {
    const ctx = await createTestCtx()
    const cookie = await ctx.login()
    const post = (path: string, body?: unknown, method = 'POST') =>
      ctx.request(path, { method, cookie, headers: { 'content-type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })

    const created = await post('/api/admin/projects', { key: 'neu', name: 'Neu' })
    expect(created.status).toBe(201)
    const { token } = await json<{ token: string }>(created)
    expect(token).toMatch(/^sak_/)

    // Liste enthält den Schlüssel nicht mehr.
    const list = await ctx.request('/api/admin/projects', { cookie })
    expect(JSON.stringify(await list.json())).not.toContain(token)

    expect((await post('/api/admin/projects', { key: 'neu', name: 'Neu' })).status).toBe(409)
    expect((await post('/api/admin/projects', { key: 'X', name: 'Neu' })).status).toBe(400)
    expect((await post('/api/admin/projects', { key: 'okay', name: '' })).status).toBe(400)

    expect((await ctx.ingestAs(token, ingestRequest('neu', []))).status).toBe(200)
    const rotated = await json<{ token: string }>(await post('/api/admin/projects/neu/rotate'))
    expect(rotated.token).not.toBe(token)
    expect((await ctx.ingestAs(token, ingestRequest('neu', []))).status).toBe(401)
    expect((await ctx.ingestAs(rotated.token, ingestRequest('neu', []))).status).toBe(200)

    expect((await post('/api/admin/projects/gibt-es-nicht/rotate')).status).toBe(404)
    expect((await post('/api/admin/projects/neu', undefined, 'DELETE')).status).toBe(200)
    expect((await post('/api/admin/projects/neu', undefined, 'DELETE')).status).toBe(404)
    expect((await ctx.ingestAs(rotated.token, ingestRequest('neu', []))).status).toBe(401)
  })

  it('löscht Events älter als die Aufbewahrungsfrist, Boards bleiben', async () => {
    const ctx = await createTestCtx()
    const token = ctx.addProject('immo-agent')
    const old = makeEvent('immo-agent', { ts: '2026-09-01T10:00:00+02:00' })
    const fresh = makeEvent('immo-agent', { ts: '2026-10-19T10:00:00+02:00' })
    await ctx.ingestAs(token, ingestRequest('immo-agent', [old, fresh], pilotBoard()))
    const result = runRetention(ctx.db, 30, ctx.clock.now)
    expect(result.eventsDeleted).toBe(1)
    const ids = (ctx.db.prepare('SELECT event_id FROM events').all() as Array<{ event_id: string }>).map((r) => r.event_id)
    expect(ids).toEqual([fresh.event_id])
    expect((ctx.db.prepare('SELECT COUNT(*) AS n FROM boards').get() as { n: number }).n).toBe(1)
  })
})
