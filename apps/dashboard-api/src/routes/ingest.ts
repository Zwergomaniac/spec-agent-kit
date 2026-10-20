import { Hono } from 'hono'
import { bodyLimit } from 'hono/body-limit'
import { LIMITS, projectKeySchema, timestampSchema } from '@sak/contracts'
import { z } from 'zod'
import type { AppDeps } from '../app.js'
import { WindowRateLimiter } from '../auth/rate-limit.js'
import { clientIp } from '../http.js'
import { ingest } from '../services/ingest.js'
import { authenticateProjectToken, type ProjectRow } from '../services/projects.js'

const INGEST_SCHEMA = 'sak.ingest/1'

// Hülle: Events werden einzeln validiert (Spec 007 FR-006), deshalb hier nur als unknown.
const envelope = z
  .object({
    schema: z.literal(INGEST_SCHEMA),
    project: projectKeySchema,
    sent_at: timestampSchema,
    events: z.array(z.unknown()).max(LIMITS.INGEST_MAX_EVENTS),
    board: z.unknown().optional()
  })
  .strict()

export function ingestRoutes(deps: AppDeps): Hono<{ Variables: { project: ProjectRow } }> {
  const app = new Hono<{ Variables: { project: ProjectRow } }>()
  const perProject = new WindowRateLimiter(60, 60_000)
  const failedAuthPerIp = new WindowRateLimiter(30, 60_000)

  app.post(
    '/',
    // 1. Authentifizieren, bevor der Body gelesen wird (401 speichert nichts).
    async (c, next) => {
      const header = c.req.header('authorization') ?? ''
      const match = /^Bearer\s+(\S+)$/i.exec(header)
      const project = match ? authenticateProjectToken(deps.db, match[1]!) : undefined
      if (!project) {
        if (!failedAuthPerIp.hit(clientIp(c, deps.env.trustProxy), deps.now())) {
          c.header('Retry-After', '60')
          return c.json({ error: 'rate_limited' }, 429)
        }
        c.header('WWW-Authenticate', 'Bearer')
        return c.json({ error: 'unauthorized' }, 401)
      }
      // 2. Rate-Limit: 60 Requests pro Minute und Projekt (FR-004).
      if (!perProject.hit(project.key, deps.now())) {
        c.header('Retry-After', '60')
        return c.json({ error: 'rate_limited' }, 429)
      }
      c.set('project', project)
      await next()
    },
    // 3. Größenlimit 2 MB, auch bei Chunked-Uploads ohne Content-Length.
    bodyLimit({
      maxSize: LIMITS.INGEST_MAX_BYTES,
      onError: (c) => c.json({ error: 'payload_too_large', max_bytes: LIMITS.INGEST_MAX_BYTES }, 413)
    }),
    async (c) => {
      const project = c.get('project')
      let raw: unknown
      try {
        raw = await c.req.json()
      } catch {
        return c.json({ error: 'invalid_json' }, 400)
      }
      if (typeof raw === 'object' && raw !== null && (raw as Record<string, unknown>).schema !== INGEST_SCHEMA) {
        return c.json({ error: `unsupported schema version (erwartet ${INGEST_SCHEMA})` }, 400)
      }
      const parsed = envelope.safeParse(raw)
      if (!parsed.success) {
        const first = parsed.error.issues[0]
        return c.json({ error: 'invalid_request', detail: first ? `${first.path.join('.') || '(root)'}: ${first.message}` : undefined }, 400)
      }
      if (parsed.data.project !== project.key) return c.json({ error: 'project mismatch' }, 403)
      const result = ingest(deps.db, project, { events: parsed.data.events, board: parsed.data.board }, deps.now())
      return c.json(result)
    }
  )

  return app
}
