import { randomBytes, scrypt, timingSafeEqual, type ScryptOptions } from 'node:crypto'

// Format: scrypt:<N>:<r>:<p>:<salt base64url>:<hash base64url>
// Bewusst ohne "$", damit der Hash ohne Escaping in .env und Compose-Dateien steht.
const N = 32768
const R = 8
const P = 1
const KEYLEN = 64
const MAXMEM = 128 * 1024 * 1024

function derive(password: string, salt: Buffer, n: number, r: number, p: number, keylen: number): Promise<Buffer> {
  const options: ScryptOptions = { N: n, r, p, maxmem: MAXMEM }
  return new Promise((resolve, reject) => {
    scrypt(password.normalize('NFKC'), salt, keylen, options, (err, key) => (err ? reject(err) : resolve(key)))
  })
}

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16)
  const key = await derive(password, salt, N, R, P, KEYLEN)
  return ['scrypt', N, R, P, salt.toString('base64url'), key.toString('base64url')].join(':')
}

/** Prüft ein Passwort gegen den gespeicherten Hash in konstanter Zeit. Ungültige Hashes ergeben false. */
export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const parts = stored.split(':')
  if (parts.length !== 6 || parts[0] !== 'scrypt') return false
  const [, nS, rS, pS, saltS, hashS] = parts as [string, string, string, string, string, string]
  const n = Number(nS)
  const r = Number(rS)
  const p = Number(pS)
  if (![n, r, p].every((v) => Number.isInteger(v) && v > 0) || n > 1 << 20) return false
  try {
    const salt = Buffer.from(saltS, 'base64url')
    const expected = Buffer.from(hashS, 'base64url')
    if (salt.length < 8 || expected.length < 16) return false
    const actual = await derive(password, salt, n, r, p, expected.length)
    return timingSafeEqual(actual, expected)
  } catch {
    return false
  }
}
