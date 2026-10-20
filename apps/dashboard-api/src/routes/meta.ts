import { Hono } from 'hono'
import { LIMITS, labels, vocabulary } from '@sak/contracts'
import { DASHBOARD_VERSION } from '../version.js'

export function metaRoutes(): Hono {
  const app = new Hono()
  app.get('/meta', (c) =>
    c.json({
      kit_version: DASHBOARD_VERSION,
      vocabulary_version: vocabulary.version,
      locale: 'de',
      vocabulary: vocabulary.levels,
      labels: labels.de,
      limits: LIMITS
    })
  )
  return app
}
