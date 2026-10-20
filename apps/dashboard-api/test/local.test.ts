import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { verifyPassword } from '../src/auth/password.js'
import { loadEnv } from '../src/env.js'
import { ensureLocalEnv, formatDotenv, localPaths, parseDotenv, serverEnv } from '../src/local/env-file.js'

const PASSWORD = 'ein-lokales-passwort-123'
let root: string

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'sak-local-'))
})
afterEach(() => {
  rmSync(root, { recursive: true, force: true })
})

describe('parseDotenv', () => {
  it('liest Werte, Anführungszeichen, Kommentare und ignoriert Müll', () => {
    const env = parseDotenv('# Kommentar\nA=1\n\nB="zwei"\nC=\'drei\'\n  D = vier \nkaputt\n=leer\n1X=nein\nE=a=b\r\n')
    expect(env).toEqual({ A: '1', B: 'zwei', C: 'drei', D: 'vier', E: 'a=b' })
  })

  it('formatDotenv und parseDotenv sind zueinander invers', () => {
    const values = { X: 'a', Y: 'scrypt:1:2:3:abc:def' }
    expect(parseDotenv(formatDotenv(values, '# Kopf\n'))).toEqual(values)
  })
})

describe('ensureLocalEnv', () => {
  it('legt beim ersten Start Secret, Pfade und nur den Hash an', async () => {
    const paths = localPaths(root)
    const prompt = vi.fn(async () => PASSWORD)
    const { env, created } = await ensureLocalEnv({ paths, promptPassword: prompt })

    expect(prompt).toHaveBeenCalledTimes(1)
    expect(created.sort()).toEqual(['SAK_ADMIN_PASSWORD_HASH', 'SAK_DB_PATH', 'SAK_SESSION_SECRET', 'SAK_WEB_DIST'])
    const file = readFileSync(paths.envFile, 'utf8')
    expect(file).not.toContain(PASSWORD)
    expect(await verifyPassword(PASSWORD, env.SAK_ADMIN_PASSWORD_HASH!)).toBe(true)
    expect(parseDotenv(file)).toEqual(env)
    expect(env.SAK_DB_PATH).toBe(paths.dbPath)
    // Die erzeugte Konfiguration besteht die Validierung des Servers.
    expect(() => loadEnv({ ...env })).not.toThrow()
  })

  it('fragt beim zweiten Start nicht erneut und lässt die Datei unverändert', async () => {
    const paths = localPaths(root)
    await ensureLocalEnv({ paths, promptPassword: async () => PASSWORD })
    const before = readFileSync(paths.envFile, 'utf8')
    const prompt = vi.fn(async () => 'darf-nicht-gefragt-werden')
    const { created } = await ensureLocalEnv({ paths, promptPassword: prompt })
    expect(prompt).not.toHaveBeenCalled()
    expect(created).toEqual([])
    expect(readFileSync(paths.envFile, 'utf8')).toBe(before)
  })

  it('lehnt zu kurze Passwörter ab und schreibt nichts', async () => {
    const paths = localPaths(root)
    await expect(ensureLocalEnv({ paths, promptPassword: async () => 'kurz' })).rejects.toThrow(/mindestens 12/)
    expect(() => readFileSync(paths.envFile)).toThrow()
  })
})

describe('serverEnv und HOST', () => {
  it('erzwingt Loopback, auch wenn die Umgebung etwas anderes setzt', () => {
    const env = serverEnv({ SAK_SESSION_SECRET: 'x' }, { HOST: '0.0.0.0' })
    expect(env.HOST).toBe('127.0.0.1')
    expect(env.NODE_ENV).toBe('development')
    expect(env.PORT).toBe('3000')
  })

  it('loadEnv: HOST ist im Container 0.0.0.0, per Variable änderbar', () => {
    const base = { SAK_ADMIN_PASSWORD_HASH: 'scrypt:x', SAK_SESSION_SECRET: 'x'.repeat(32) }
    expect(loadEnv(base).host).toBe('0.0.0.0')
    expect(loadEnv({ ...base, HOST: '127.0.0.1' }).host).toBe('127.0.0.1')
  })
})
