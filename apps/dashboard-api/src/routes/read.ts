import { Hono } from 'hono'
import { LIMITS, projectKeySchema, runIdSchema, timestampSchema } from '@sak/contracts'
import type { AppDeps } from '../app.js'
import { toUtc } from '../db.js'
import { buildPortfolio } from '../services/portfolio.js'
import { getProject } from '../services/projects.js'
import { countEvents, getBoard, getRunDetail, listEvents } from '../services/runs.js'

export function readRoutes(deps: AppDeps): Hono {
  const app = new Hono()

  app.get('/portfolio', (c) => c.json(buildPortfolio(deps.db, deps.now())))

  app.get('/projects/:key', (c) => {
    const key = c.req.param('key')
    const project = projectKeySchema.safeParse(key).success ? getProject(deps.db, key) : undefined
    if (!project) return c.json({ error: 'not_found' }, 404)
    const stored = getBoard(deps.db, key)
    return c.json({
      project: { key: project.key, name: project.name },
      board: stored?.board ?? null,
      ingest: {
        last_ingest_at: project.last_ingest_at,
        board_received_at: stored?.received_at ?? null,
        event_count: countEvents(deps.db, key)
      }
    })
  })

  app.get('/projects/:key/runs/:runId', (c) => {
    const key = c.req.param('key')
    const runId = c.req.param('runId')
    if (!projectKeySchema.safeParse(key).success || !runIdSchema.safeParse(runId).success || !getProject(deps.db, key)) {
      return c.json({ error: 'not_found' }, 404)
    }
    const detail = getRunDetail(deps.db, key, runId)
    if (!detail) return c.json({ error: 'not_found' }, 404)
    return c.json(detail)
  })

  app.get('/projects/:key/events', (c) => {
    const key = c.req.param('key')
    if (!projectKeySchema.safeParse(key).success || !getProject(deps.db, key)) return c.json({ error: 'not_found' }, 404)

    const run = c.req.query('run')
    if (run !== undefined && !runIdSchema.safeParse(run).success) return c.json({ error: 'invalid_run' }, 400)

    const since = c.req.query('since')
    if (since !== undefined && !timestampSchema.safeParse(since).success) return c.json({ error: 'invalid_since' }, 400)

    const limitRaw = c.req.query('limit')
    let limit = 100
    if (limitRaw !== undefined) {
      limit = Number(limitRaw)
      if (!Number.isInteger(limit) || limit < 1 || limit > LIMITS.INGEST_MAX_EVENTS) return c.json({ error: 'invalid_limit' }, 400)
    }

    const events = listEvents(deps.db, key, { run, since: since ? toUtc(since) : undefined, limit })
    return c.json({ events })
  })

  return app
}
