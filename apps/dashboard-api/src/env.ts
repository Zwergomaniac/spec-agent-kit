// Konfiguration nur über Umgebungsvariablen (Spec 007 FR-001).
export interface Env {
  nodeEnv: string
  /** Cookie-Flag Secure; nur bei NODE_ENV=development aus (Spec 007, Annahmen). */
  secureCookie: boolean
  port: number
  adminPasswordHash: string
  sessionSecret: string
  dbPath: string
  retentionDays: number
  trustProxy: boolean
  webDist: string | null
}

export class EnvError extends Error {
  constructor(public readonly problems: string[]) {
    super(`Ungültige Konfiguration:\n - ${problems.join('\n - ')}`)
    this.name = 'EnvError'
  }
}

function parseBool(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined || value === '') return fallback
  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase())
}

function parsePositiveInt(name: string, value: string | undefined, fallback: number, problems: string[]): number {
  if (value === undefined || value === '') return fallback
  const n = Number(value)
  if (!Number.isInteger(n) || n < 1) {
    problems.push(`${name} muss eine positive ganze Zahl sein.`)
    return fallback
  }
  return n
}

export function loadEnv(source: Record<string, string | undefined> = process.env): Env {
  const problems: string[] = []

  const adminPasswordHash = source.SAK_ADMIN_PASSWORD_HASH ?? ''
  if (!adminPasswordHash) {
    problems.push('SAK_ADMIN_PASSWORD_HASH fehlt (erzeugen mit: node dist/cli/hash-password.js).')
  } else if (!adminPasswordHash.startsWith('scrypt:')) {
    problems.push('SAK_ADMIN_PASSWORD_HASH hat kein gültiges Format (erwartet: scrypt:...).')
  }

  const sessionSecret = source.SAK_SESSION_SECRET ?? ''
  if (!sessionSecret) {
    problems.push('SAK_SESSION_SECRET fehlt (mindestens 32 zufällige Zeichen).')
  } else if (sessionSecret.length < 32) {
    problems.push('SAK_SESSION_SECRET ist zu kurz (mindestens 32 Zeichen).')
  }

  const retentionDays = parsePositiveInt('SAK_RETENTION_DAYS', source.SAK_RETENTION_DAYS, 30, problems)
  const port = parsePositiveInt('PORT', source.PORT, 3000, problems)

  if (problems.length > 0) throw new EnvError(problems)

  const nodeEnv = source.NODE_ENV ?? 'production'
  return {
    nodeEnv,
    secureCookie: nodeEnv !== 'development',
    port,
    adminPasswordHash,
    sessionSecret,
    dbPath: source.SAK_DB_PATH || '/data/dashboard.db',
    retentionDays,
    trustProxy: parseBool(source.SAK_TRUST_PROXY, true),
    webDist: source.SAK_WEB_DIST || null
  }
}
