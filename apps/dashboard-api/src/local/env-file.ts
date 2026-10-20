// Lokaler Modus (Spec 009 US3): .local/dashboard.env lesen, ergänzen und schreiben.
// Gespeichert werden nur Session-Secret, DB-Pfad, Web-Pfad und der scrypt-Hash, nie das Passwort.
import { randomBytes } from 'node:crypto'
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { hashPassword } from '../auth/password.js'

export type EnvMap = Record<string, string>

/** Kleiner dotenv-Parser: KEY=wert, optionale Anführungszeichen, `#`-Kommentare, leere Zeilen. */
export function parseDotenv(text: string): EnvMap {
  const out: EnvMap = {}
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim()
    if (line === '' || line.startsWith('#')) continue
    const eq = line.indexOf('=')
    if (eq < 1) continue
    const key = line.slice(0, eq).trim()
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) continue
    let value = line.slice(eq + 1).trim()
    const quote = value[0]
    if ((quote === '"' || quote === "'") && value.length >= 2 && value.endsWith(quote)) value = value.slice(1, -1)
    out[key] = value
  }
  return out
}

export function formatDotenv(values: EnvMap, header = ''): string {
  const body = Object.entries(values)
    .map(([k, v]) => `${k}=${v}`)
    .join('\n')
  return `${header}${body}\n`
}

export const LOCAL_ENV_HEADER =
  '# Lokale Dashboard-Konfiguration (von `pnpm dashboard:local` angelegt, gitignored).\n# Enthält nur den Hash des Admin-Passworts, nie das Passwort selbst.\n'

export interface LocalPaths {
  dir: string
  envFile: string
  dbPath: string
  webDist: string
}

export function localPaths(repoRoot: string): LocalPaths {
  const dir = join(repoRoot, '.local')
  return {
    dir,
    envFile: join(dir, 'dashboard.env'),
    dbPath: join(dir, 'dashboard.db'),
    webDist: join(repoRoot, 'apps', 'dashboard-web', 'dist')
  }
}

export interface EnsureOptions {
  paths: LocalPaths
  /** Fragt das Admin-Passwort ab; wird nur aufgerufen, wenn noch kein Hash existiert. */
  promptPassword: () => Promise<string>
  randomSecret?: () => string
}

export interface EnsureResult {
  env: EnvMap
  created: string[]
}

export const MIN_PASSWORD_LENGTH = 12

/** Ergänzt fehlende Schlüssel in .local/dashboard.env. Vorhandene Werte bleiben unangetastet. */
export async function ensureLocalEnv(opts: EnsureOptions): Promise<EnsureResult> {
  const { paths } = opts
  const env: EnvMap = existsSync(paths.envFile) ? parseDotenv(readFileSync(paths.envFile, 'utf8')) : {}
  const created: string[] = []
  const randomSecret = opts.randomSecret ?? ((): string => randomBytes(48).toString('base64url'))

  if (!env.SAK_SESSION_SECRET || env.SAK_SESSION_SECRET.length < 32) {
    env.SAK_SESSION_SECRET = randomSecret()
    created.push('SAK_SESSION_SECRET')
  }
  if (!env.SAK_DB_PATH) {
    env.SAK_DB_PATH = paths.dbPath
    created.push('SAK_DB_PATH')
  }
  if (!env.SAK_WEB_DIST) {
    env.SAK_WEB_DIST = paths.webDist
    created.push('SAK_WEB_DIST')
  }
  if (!env.SAK_ADMIN_PASSWORD_HASH?.startsWith('scrypt:')) {
    const password = await opts.promptPassword()
    if (password.length < MIN_PASSWORD_LENGTH) throw new Error(`Das Passwort muss mindestens ${MIN_PASSWORD_LENGTH} Zeichen lang sein.`)
    env.SAK_ADMIN_PASSWORD_HASH = await hashPassword(password)
    created.push('SAK_ADMIN_PASSWORD_HASH')
  }

  if (created.length > 0) {
    mkdirSync(dirname(paths.envFile), { recursive: true })
    writeFileSync(paths.envFile, formatDotenv(env, LOCAL_ENV_HEADER), { encoding: 'utf8', mode: 0o600 })
    try {
      chmodSync(paths.envFile, 0o600)
    } catch {
      // Windows kennt kein chmod im POSIX-Sinn; ignorieren.
    }
  }
  return { env, created }
}

/** Env für den lokalen Server: Datei-Werte, Loopback erzwungen, Entwicklungsmodus (Cookie ohne Secure). */
export function serverEnv(fileEnv: EnvMap, base: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  return {
    ...base,
    ...fileEnv,
    NODE_ENV: 'development',
    HOST: '127.0.0.1',
    SAK_TRUST_PROXY: 'false',
    PORT: base.PORT || '3000'
  }
}
