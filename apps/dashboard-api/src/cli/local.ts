// Lokaler Betrieb (Spec 009 US3). Aufruf über apps/dashboard-api/scripts/local.mjs:
//   pnpm dashboard:local                       Server auf http://127.0.0.1:3000
//   pnpm dashboard:project add <key> <name>    Projekte verwalten (list|rotate|remove)
// Das Passwort wird einmalig verdeckt abgefragt; gespeichert wird nur der Hash.
import { spawn } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { ensureLocalEnv, localPaths, serverEnv } from '../local/env-file.js'
import { readHidden, readStdin } from './prompt.js'

async function promptPassword(): Promise<string> {
  if (!process.stdin.isTTY) return readStdin()
  process.stderr.write('Einmalige Einrichtung des lokalen Dashboards.\n')
  const password = await readHidden('Lokales Admin-Passwort (mindestens 12 Zeichen): ')
  const again = await readHidden('Wiederholen: ')
  if (password !== again) throw new Error('Die Eingaben stimmen nicht überein.')
  return password
}

function run(script: string, args: string[], env: NodeJS.ProcessEnv): Promise<number> {
  const child = spawn(process.execPath, [script, ...args], { stdio: 'inherit', env })
  const forward = (sig: NodeJS.Signals) => (): void => void child.kill(sig)
  process.on('SIGINT', forward('SIGINT'))
  process.on('SIGTERM', forward('SIGTERM'))
  return new Promise((res) => child.on('exit', (code) => res(code ?? 1)))
}

async function main(): Promise<void> {
  const distDir = dirname(fileURLToPath(import.meta.url)) // apps/dashboard-api/dist/cli
  const apiDist = resolve(distDir, '..')
  const repoRoot = resolve(apiDist, '..', '..', '..')
  const paths = localPaths(repoRoot)
  const [command, ...rest] = process.argv.slice(2)

  mkdirSync(paths.dir, { recursive: true })
  const { env, created } = await ensureLocalEnv({ paths, promptPassword })
  if (created.length > 0) process.stderr.write(`Angelegt in ${paths.envFile}: ${created.join(', ')}\n`)

  const senv = serverEnv(env)
  if (command === 'project') {
    process.exit(await run(resolve(apiDist, 'cli', 'project.js'), rest, senv))
  }
  process.stderr.write(`Dashboard lokal: http://127.0.0.1:${senv.PORT} (nur Loopback, Abbruch mit Strg+C)\n`)
  process.exit(await run(resolve(apiDist, 'server.js'), [], senv))
}

main().catch((err: unknown) => {
  process.stderr.write(`Fehler: ${err instanceof Error ? err.message : String(err)}\n`)
  process.exit(1)
})
