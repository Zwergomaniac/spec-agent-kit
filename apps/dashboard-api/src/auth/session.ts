import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto'

export const SESSION_COOKIE = 'sak_session'
export const SESSION_TTL_S = 12 * 60 * 60

interface SessionPayload {
  /** Ablaufzeit, Unix-Sekunden. */
  exp: number
  /** Ausgestellt, Unix-Sekunden. */
  iat: number
  /** Zufällige Kennung, damit jede Session ein eigenes Cookie hat. */
  sid: string
}

function sign(body: string, secret: string): string {
  return createHmac('sha256', secret).update(body).digest('base64url')
}

/** Signiertes, zustandsloses Cookie: base64url(JSON).HMAC-SHA256. */
export function createSessionToken(secret: string, nowMs: number = Date.now()): string {
  const iat = Math.floor(nowMs / 1000)
  const payload: SessionPayload = { iat, exp: iat + SESSION_TTL_S, sid: randomBytes(12).toString('base64url') }
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url')
  return `${body}.${sign(body, secret)}`
}

export function verifySessionToken(token: string | undefined, secret: string, nowMs: number = Date.now()): boolean {
  if (!token) return false
  const parts = token.split('.')
  if (parts.length !== 2) return false
  const [body, mac] = parts as [string, string]
  const expected = Buffer.from(sign(body, secret))
  const given = Buffer.from(mac)
  if (expected.length !== given.length || !timingSafeEqual(expected, given)) return false
  try {
    const payload = JSON.parse(Buffer.from(body, 'base64url').toString('utf8')) as Partial<SessionPayload>
    return typeof payload.exp === 'number' && payload.exp > Math.floor(nowMs / 1000)
  } catch {
    return false
  }
}
