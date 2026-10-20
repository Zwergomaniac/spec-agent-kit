// Einstieg für `pnpm dashboard:local` und `pnpm dashboard:project` (plattformneutral, ohne Abhängigkeiten).
// Baut bei Bedarf (fehlende dist-Ordner oder --rebuild) und startet dann dist/cli/local.js.
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const apiDir = fileURLToPath(new URL('..', import.meta.url))
const repoRoot = fileURLToPath(new URL('../../..', import.meta.url))
const args = process.argv.slice(2)
const rebuild = args.includes('--rebuild')
const passArgs = args.filter((a) => a !== '--rebuild')

const needed = [
  `${apiDir}dist/cli/local.js`,
  `${apiDir}dist/server.js`,
  `${apiDir}dist/cli/project.js`,
  `${repoRoot}apps/dashboard-web/dist/index.html`
]
if (rebuild || needed.some((f) => !existsSync(f))) {
  console.error('Baue Dashboard (pnpm -r build) ...')
  const build = spawnSync('pnpm', ['-r', 'build'], { cwd: repoRoot, stdio: 'inherit', shell: process.platform === 'win32' })
  if (build.status !== 0) {
    console.error('Build fehlgeschlagen.')
    process.exit(build.status ?? 1)
  }
}

const result = spawnSync(process.execPath, [`${apiDir}dist/cli/local.js`, ...passArgs], { stdio: 'inherit' })
process.exit(result.status ?? 1)
