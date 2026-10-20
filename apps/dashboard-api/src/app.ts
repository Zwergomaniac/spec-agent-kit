import { Hono } from 'hono'
import { HTTPException } from 'hono/http-exception'
import { secureHeaders } from 'hono/secure-headers'
import type { Db } from './db.js'
import type { Env } from './env.js'
import { requireSession, sameOriginForWrites } from './http.js'
import { adminRoutes } from './routes/admin.js'
import { authRoutes } from './routes/auth.js'
import { healthRoutes } from './routes/health.js'
import { ingestRoutes } from './routes/ingest.js'
import { metaRoutes } from './routes/meta.js'
import { readRoutes } from './routes/read.js'
import { createStaticHandler } from './static.js'

export interface AppDeps {
  db: Db
  env: Pick<Env, 'sessionSecret' | 'adminPasswordHash' | 'secureCookie' | 'trustProxy' | 'webDist'>
  /** Aktuelle Zeit in ms; in Tests ersetzbar. */
  now: () => number
}

/** Baut die Hono-App ohne Netzwerk, damit sie mit `app.request()` testbar ist. */
export function createApp(deps: AppDeps): Hono {
  const app = new Hono()

  app.use(
    '*',
    secureHeaders({
      contentSecurityPolicy: {
        defaultSrc: ["'self'"],
        scriptSrc: ["'self'"],
        // Tailwind liefert Dateien; Recharts und React setzen Inline-Styles.
        styleSrc: ["'self'", "'unsafe-inline'"],
        imgSrc: ["'self'", 'data:'],
        connectSrc: ["'self'"],
        frameAncestors: ["'none'"],
        baseUri: ["'self'"],
        formAction: ["'self'"]
      },
      referrerPolicy: 'no-referrer'
    })
  )
  app.use('/api/*', async (c, next) => {
    await next()
    c.header('Cache-Control', 'no-store')
  })
  app.use('/api/*', sameOriginForWrites(deps))

  app.route('/', healthRoutes(deps))
  app.route('/api/auth', authRoutes(deps))
  app.route('/api/ingest', ingestRoutes(deps))

  // Alles übrige unter /api verlangt eine Session.
  const session = requireSession(deps)
  app.use('/api/meta', session)
  app.use('/api/portfolio', session)
  app.use('/api/projects/*', session)
  app.use('/api/admin/*', session)
  app.route('/api', metaRoutes())
  app.route('/api', readRoutes(deps))
  app.route('/api/admin', adminRoutes(deps))

  app.onError((err, c) => {
    if (err instanceof HTTPException) return err.getResponse()
    // Nur der Fehlername wird protokolliert: keine Stacktraces nach außen, keine Request-Bodies (FR-007).
    console.error(`unhandled error: ${err.name}`)
    return c.json({ error: 'internal_error' }, 500)
  })

  if (deps.env.webDist) {
    app.notFound(createStaticHandler(deps.env.webDist))
  } else {
    app.notFound((c) => c.json({ error: 'not_found' }, 404))
  }

  return app
}
