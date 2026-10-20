import { Hono } from 'hono'
import type { AppDeps } from '../app.js'

export function healthRoutes(deps: AppDeps): Hono {
  const app = new Hono()
  app.get('/healthz', (c) => {
    // Kurzer DB-Zugriff, damit ein defekter Datenspeicher den Healthcheck fehlschlagen lässt.
    deps.db.prepare('SELECT 1').get()
    return c.json({ status: 'ok' })
  })
  return app
}
