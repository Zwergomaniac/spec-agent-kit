// Mock von `sak board serve` (Spec 010 FR-001): liefert die gebaute lokale UI (board/web/) und dieselben
// Lese-Endpunkte in der Form des zentralen Dashboards, ohne Auth. Nur für E2E-Tests.
import { labels, LIMITS, vocabulary, type Board, type SakEvent } from '@sak/contracts'
import { readFile } from 'node:fs/promises'
import { createServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { extname, join, normalize, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

export const WEB_DIR = fileURLToPath(new URL('../../../packages/engine/src/spec_agent_kit/board/web/', import.meta.url))

const TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml'
}

export interface MockBoardServer {
  url: string
  /** Alle bisher angefragten Pfade (mit Query), damit Tests z. B. fehlende Auth-Aufrufe prüfen können. */
  requests: string[]
  close: () => Promise<void>
}

export async function startMockBoardServer(board: Board, events: SakEvent[]): Promise<MockBoardServer> {
  const key = board.project.key
  const requests: string[] = []

  const server: Server = createServer(async (req, res) => {
    const url = new URL(req.url ?? '/', 'http://127.0.0.1')
    requests.push(url.pathname + url.search)
    const json = (status: number, body: unknown): void => {
      res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' })
      res.end(JSON.stringify(body))
    }
    if (req.method !== 'GET') return json(405, { error: 'method_not_allowed' })

    if (url.pathname === '/api/meta') {
      return json(200, {
        kit_version: board.kit_version,
        vocabulary_version: vocabulary.version,
        locale: 'de',
        vocabulary: vocabulary.levels,
        labels: labels.de,
        limits: LIMITS,
        mode: 'local',
        project_key: key
      })
    }
    const m = /^\/api\/projects\/([^/]+)(?:\/(runs\/([^/]+)|events))?$/.exec(url.pathname)
    if (m) {
      if (decodeURIComponent(m[1]!) !== key) return json(404, { error: 'not_found' })
      if (!m[2]) {
        return json(200, {
          project: { key, name: board.project.name },
          board,
          ingest: { last_ingest_at: null, board_received_at: null, event_count: events.length }
        })
      }
      if (m[3]) {
        const runId = decodeURIComponent(m[3])
        const run = board.runs.find((r) => r.run_id === runId)
        if (!run) return json(404, { error: 'not_found' })
        return json(200, { project: key, run, events: events.filter((e) => e.run_id === runId) })
      }
      const run = url.searchParams.get('run')
      const since = url.searchParams.get('since')
      const limit = Number(url.searchParams.get('limit') ?? 100)
      const list = events
        .filter((e) => (run === null || e.run_id === run) && (since === null || Date.parse(e.ts) > Date.parse(since)))
        .slice(0, limit)
      return json(200, { events: list })
    }
    if (url.pathname.startsWith('/api/')) return json(404, { error: 'not_found' })

    // Statische Dateien aus board/web/.
    const rel = url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname.slice(1))
    const file = normalize(join(WEB_DIR, rel))
    if (!file.startsWith(WEB_DIR.replace(/[\\/]$/, '') + sep)) return json(403, { error: 'forbidden' })
    try {
      const body = await readFile(file)
      res.writeHead(200, { 'content-type': TYPES[extname(file)] ?? 'application/octet-stream' })
      res.end(body)
    } catch {
      json(404, { error: 'not_found' })
    }
  })

  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
  const port = (server.address() as AddressInfo).port
  return {
    url: `http://127.0.0.1:${port}`,
    requests,
    close: () => new Promise<void>((resolve) => server.close(() => resolve()))
  }
}
