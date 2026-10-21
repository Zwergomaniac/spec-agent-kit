import { LIMITS, type IngestResult } from '@sak/contracts'
import { beforeEach, describe, expect, it } from 'vitest'
import { createTestCtx, ingestRequest, loadExample, makeEvent, pilotBoard, type TestCtx } from './helpers.js'

const count = (ctx: TestCtx, table: string): number =>
  (ctx.db.prepare(`SELECT COUNT(*) AS n FROM ${table}`).get() as { n: number }).n

describe('POST /api/ingest (Vertragstests, SC-002)', () => {
  let ctx: TestCtx
  let tokenA: string

  beforeEach(async () => {
    ctx = await createTestCtx()
    tokenA = ctx.addProject('proj-a')
    ctx.addProject('proj-b')
  })

  it('401 ohne Schlüssel, nichts wird gespeichert', async () => {
    const res = await ctx.request('/api/ingest', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(ingestRequest('proj-a', [makeEvent('proj-a')]))
    })
    expect(res.status).toBe(401)
    expect(count(ctx, 'events')).toBe(0)
  })

  it('401 mit falschem Schlüssel, nichts wird gespeichert', async () => {
    const res = await ctx.ingestAs('sak_falsch', ingestRequest('proj-a', [makeEvent('proj-a')], undefined))
    expect(res.status).toBe(401)
    expect(count(ctx, 'events')).toBe(0)
    expect(count(ctx, 'boards')).toBe(0)
  })

  it('401 bei Schlüssel eines entfernten Projekts', async () => {
    const res = await ctx.ingestAs(tokenA, ingestRequest('proj-a', [makeEvent('proj-a')]))
    expect(res.status).toBe(200)
    ctx.db.prepare('DELETE FROM projects WHERE key = ?').run('proj-a')
    const again = await ctx.ingestAs(tokenA, ingestRequest('proj-a', [makeEvent('proj-a')]))
    expect(again.status).toBe(401)
  })

  it('413 bei Requests über 2 MB, auch ohne Content-Length-Angabe', async () => {
    const padding = 'x'.repeat(LIMITS.INGEST_MAX_BYTES + 10)
    const res = await ctx.ingestAs(tokenA, `{"schema":"sak.ingest/1","pad":"${padding}"}`)
    expect(res.status).toBe(413)
    expect(count(ctx, 'events')).toBe(0)
  })

  it('nimmt gültige Events an und aktualisiert last_ingest_at', async () => {
    const events = [makeEvent('proj-a'), makeEvent('proj-a')]
    const res = await ctx.ingestAs(tokenA, ingestRequest('proj-a', events))
    expect(res.status).toBe(200)
    const body = (await res.json()) as IngestResult
    expect(body).toEqual({ schema: 'sak.ingest_result/1', accepted: 2, duplicates: 0, rejected: [], board_accepted: false })
    expect(count(ctx, 'events')).toBe(2)
    const row = ctx.db.prepare('SELECT last_ingest_at FROM projects WHERE key = ?').get('proj-a') as { last_ingest_at: string }
    expect(row.last_ingest_at).toBe(new Date(ctx.clock.now).toISOString())
  })

  it('lehnt Events fremder Projekte ab: "project mismatch"', async () => {
    const foreign = makeEvent('proj-b')
    const own = makeEvent('proj-a')
    const res = await ctx.ingestAs(tokenA, ingestRequest('proj-a', [foreign, own]))
    const body = (await res.json()) as IngestResult
    expect(res.status).toBe(200)
    expect(body.accepted).toBe(1)
    expect(body.rejected).toEqual([{ event_id: foreign.event_id, error: 'project mismatch' }])
    expect(count(ctx, 'events')).toBe(1)
  })

  it('lehnt eine Hülle für ein anderes Projekt als das des Schlüssels ab (403)', async () => {
    const res = await ctx.ingestAs(tokenA, ingestRequest('proj-b', [makeEvent('proj-b')]))
    expect(res.status).toBe(403)
    // Das erwartete Projekt wird genannt (nie der Schlüssel), damit der Push-Client es melden kann.
    expect(await res.json()).toEqual({ error: 'project mismatch', expected: 'proj-a' })
    expect(count(ctx, 'events')).toBe(0)
  })

  it('erkennt Duplikate an der event_id, auch im selben Batch', async () => {
    const event = makeEvent('proj-a')
    const first = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [event, event]))).json()) as IngestResult
    expect(first).toMatchObject({ accepted: 1, duplicates: 1 })
    const second = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [event]))).json()) as IngestResult
    expect(second).toMatchObject({ accepted: 0, duplicates: 1, rejected: [] })
    expect(count(ctx, 'events')).toBe(1)
  })

  it('lehnt ungültige Events einzeln ab und nimmt den Rest an', async () => {
    const good = makeEvent('proj-a')
    const badEnum = { ...makeEvent('proj-a'), type: 'run.exploded' }
    const unknownField = { ...makeEvent('proj-a'), extra: 'x' }
    const badData = { ...makeEvent('proj-a'), data: { round: 0 } }
    const res = await ctx.ingestAs(tokenA, ingestRequest('proj-a', [badEnum, good, unknownField, badData] as never))
    const body = (await res.json()) as IngestResult
    expect(res.status).toBe(200)
    expect(body.accepted).toBe(1)
    expect(body.rejected).toHaveLength(3)
    expect(body.rejected.map((r) => r.event_id)).toEqual([badEnum.event_id, unknownField.event_id, badData.event_id])
    expect(count(ctx, 'events')).toBe(1)
  })

  it('lehnt Events mit unbekannter Hauptversion ab', async () => {
    const v2 = { ...makeEvent('proj-a'), schema: 'sak.event/2' }
    const body = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [v2] as never))).json()) as IngestResult
    expect(body.accepted).toBe(0)
    expect(body.rejected[0]?.error).toMatch(/unsupported schema version/)
  })

  it('lehnt Requests mit unbekannter Ingest-Version ab (400)', async () => {
    const res = await ctx.ingestAs(tokenA, { ...ingestRequest('proj-a', []), schema: 'sak.ingest/2' })
    expect(res.status).toBe(400)
  })

  it('lehnt kaputtes JSON ab (400)', async () => {
    const res = await ctx.ingestAs(tokenA, '{nicht json')
    expect(res.status).toBe(400)
  })

  it('lehnt Events über 8 KB einzeln ab', async () => {
    const big = { ...makeEvent('proj-a'), junk: 'x'.repeat(LIMITS.EVENT_MAX_BYTES) }
    const body = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [big, makeEvent('proj-a')] as never))).json()) as IngestResult
    expect(body.accepted).toBe(1)
    expect(body.rejected[0]?.error).toMatch(/zu groß/)
  })

  it('lehnt mehr als 500 Events pro Request ab (400)', async () => {
    const events = Array.from({ length: LIMITS.INGEST_MAX_EVENTS + 1 }, () => makeEvent('proj-a'))
    const res = await ctx.ingestAs(tokenA, ingestRequest('proj-a', events))
    expect(res.status).toBe(400)
  })

  it('übernimmt ein gültiges Board und verwirft ein veraltetes', async () => {
    const board = { ...pilotBoard(), project: { key: 'proj-a', name: 'Projekt A', base_branch: 'main' } }
    const first = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [], board))).json()) as IngestResult
    expect(first.board_accepted).toBe(true)

    const older = { ...board, generated_at: '2026-10-19T08:00:00+02:00', metrics: { ...board.metrics, done: 99 } }
    const stale = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [], older))).json()) as IngestResult
    expect(stale).toMatchObject({ board_accepted: false, rejected: [] })

    const same = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [], board))).json()) as IngestResult
    expect(same.board_accepted).toBe(false)

    const row = ctx.db.prepare('SELECT body FROM boards WHERE project = ?').get('proj-a') as { body: string }
    expect(JSON.parse(row.body).metrics.done).toBe(board.metrics.done)

    const newer = { ...board, generated_at: '2026-10-20T11:00:00+02:00', metrics: { ...board.metrics, done: 5 } }
    const updated = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [], newer))).json()) as IngestResult
    expect(updated.board_accepted).toBe(true)
    expect(count(ctx, 'boards')).toBe(1)
  })

  it('vergleicht Board-Zeitpunkte über Zeitzonen hinweg korrekt', async () => {
    const board = { ...pilotBoard(), project: { key: 'proj-a', name: 'A', base_branch: 'main' } }
    // 10:20+02:00 == 08:20Z. 08:30Z ist neuer, obwohl "08:30" lexikografisch vor "10:20" liegt.
    await ctx.ingestAs(tokenA, ingestRequest('proj-a', [], board))
    const later = { ...board, generated_at: '2026-10-20T08:30:00Z' }
    const res = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [], later))).json()) as IngestResult
    expect(res.board_accepted).toBe(true)
  })

  it('lehnt ein Board eines fremden Projekts ab', async () => {
    const res = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [], pilotBoard()))).json()) as IngestResult
    expect(res.board_accepted).toBe(false)
    expect(res.rejected[0]?.error).toBe('board: project mismatch')
    expect(count(ctx, 'boards')).toBe(0)
  })

  it('lehnt ein ungültiges Board ab, ohne es zu speichern', async () => {
    const broken = { ...pilotBoard(), project: { key: 'proj-a', name: 'A', base_branch: 'main' }, surprise: true }
    const res = (await (await ctx.ingestAs(tokenA, ingestRequest('proj-a', [], broken as never))).json()) as IngestResult
    expect(res.board_accepted).toBe(false)
    expect(res.rejected[0]?.error).toMatch(/^board: ungültig/)
    expect(count(ctx, 'boards')).toBe(0)
  })

  it('nimmt das Beispiel-Ingest-Request aus den Contracts an', async () => {
    const token = ctx.addProject('immo-agent')
    const withEvents = await ctx.ingestAs(token, loadExample<unknown>('ingest-request.json') as never)
    const first = (await withEvents.json()) as IngestResult
    expect(withEvents.status).toBe(200)
    expect(first).toMatchObject({ accepted: 2, duplicates: 0, rejected: [], board_accepted: false })

    const withBoard = await ctx.ingestAs(token, loadExample<unknown>('ingest-request-with-board.json') as never)
    const second = (await withBoard.json()) as IngestResult
    expect(second).toMatchObject({ rejected: [], board_accepted: true })
  })

  it('begrenzt auf 60 Requests pro Minute und Projekt (429), andere Projekte bleiben unberührt', async () => {
    const tokenB = ctx.addProject('proj-c')
    for (let i = 0; i < 60; i += 1) {
      const res = await ctx.ingestAs(tokenA, ingestRequest('proj-a', []))
      expect(res.status).toBe(200)
    }
    const blocked = await ctx.ingestAs(tokenA, ingestRequest('proj-a', []))
    expect(blocked.status).toBe(429)
    expect((await ctx.ingestAs(tokenB, ingestRequest('proj-c', []))).status).toBe(200)
    ctx.clock.now += 61_000
    expect((await ctx.ingestAs(tokenA, ingestRequest('proj-a', []))).status).toBe(200)
  })

  it('speichert nur die validierten Contract-Daten (kein Request-Body-Rest)', async () => {
    const event = makeEvent('proj-a')
    await ctx.ingestAs(tokenA, ingestRequest('proj-a', [event]))
    const row = ctx.db.prepare('SELECT body FROM events WHERE event_id = ?').get(event.event_id) as { body: string }
    expect(JSON.parse(row.body)).toEqual(event)
  })

  it('speichert den Projekt-Schlüssel nur als SHA-256-Hash', () => {
    const rows = ctx.db.prepare('SELECT token_hash FROM projects').all() as Array<{ token_hash: string }>
    for (const r of rows) {
      expect(r.token_hash).toMatch(/^[0-9a-f]{64}$/)
      expect(r.token_hash).not.toContain(tokenA)
    }
  })
})
