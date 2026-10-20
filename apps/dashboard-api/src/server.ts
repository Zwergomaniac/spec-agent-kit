import { serve } from '@hono/node-server'
import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createApp } from './app.js'
import { openDb } from './db.js'
import { EnvError, loadEnv, type Env } from './env.js'
import { startRetention } from './services/retention.js'

function defaultWebDist(): string | null {
  // dist/server.js liegt in apps/dashboard-api/dist, die UI in apps/dashboard-web/dist.
  const here = dirname(fileURLToPath(import.meta.url))
  const candidate = resolve(here, '../../dashboard-web/dist')
  return existsSync(candidate) ? candidate : null
}

function main(): void {
  let env: Env
  try {
    env = loadEnv()
  } catch (err) {
    if (err instanceof EnvError) {
      console.error(err.message)
      process.exit(1)
    }
    throw err
  }

  const webDist = env.webDist ?? defaultWebDist()
  const db = openDb(env.dbPath)
  const stopRetention = startRetention(db, env.retentionDays)
  const app = createApp({ db, env: { ...env, webDist }, now: Date.now })

  const server = serve({ fetch: app.fetch, port: env.port, hostname: env.host }, (info) => {
    console.log(`dashboard listening on ${info.address}:${info.port} (ui: ${webDist ?? 'nicht gefunden'})`)
  })

  const shutdown = (): void => {
    stopRetention()
    server.close(() => {
      db.close()
      process.exit(0)
    })
    setTimeout(() => process.exit(0), 3000).unref()
  }
  process.on('SIGTERM', shutdown)
  process.on('SIGINT', shutdown)
}

main()
