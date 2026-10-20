// E2E gegen den echten API-Server mit gebauter UI (Voraussetzung: `pnpm -r build`).
// Der Server läuft auf Port 3100 mit frischer SQLite-Datei und Test-Secrets (nur für lokale Tests).
import { defineConfig, devices } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdirSync, rmSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { ADMIN_PASSWORD, BASE_URL, SESSION_SECRET } from './e2e/fixtures'

const apiDir = fileURLToPath(new URL('../dashboard-api/', import.meta.url))
const tmpDir = fileURLToPath(new URL('./e2e/.tmp/', import.meta.url))

// Nur im Hauptprozess vorbereiten (Worker laden die Config erneut).
const hash = execFileSync(process.execPath, ['dist/cli/hash-password.js'], { cwd: apiDir, input: ADMIN_PASSWORD, encoding: 'utf8' }).trim()
if (!process.env.TEST_WORKER_INDEX) {
  rmSync(tmpDir, { recursive: true, force: true })
  mkdirSync(tmpDir, { recursive: true })
}

export default defineConfig({
  testDir: './e2e',
  testMatch: /.*\.spec\.ts/,
  globalSetup: './e2e/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: BASE_URL, locale: 'de-DE', timezoneId: 'Europe/Berlin', trace: 'off' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'node dist/server.js',
    cwd: apiDir,
    url: `${BASE_URL}/healthz`,
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      NODE_ENV: 'development',
      PORT: '3100',
      SAK_ADMIN_PASSWORD_HASH: hash,
      SAK_SESSION_SECRET: SESSION_SECRET,
      SAK_DB_PATH: `${tmpDir}e2e.db`
    }
  }
})
