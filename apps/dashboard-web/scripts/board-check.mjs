// Baut die lokale UI neu und prüft, dass das eingecheckte Verzeichnis board/web/ aktuell ist
// (git diff --exit-code plus keine unversionierten Dateien). Aufruf: pnpm board:check
import { execFileSync, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../../', import.meta.url))
const target = 'packages/engine/src/spec_agent_kit/board/web'
const pnpm = process.platform === 'win32' ? 'pnpm.cmd' : 'pnpm'

const build = spawnSync(pnpm, ['--filter', '@sak/dashboard-web', 'run', 'build:local'], { cwd: root, stdio: 'inherit', shell: process.platform === 'win32' })
if (build.status !== 0) process.exit(build.status ?? 1)

const diff = spawnSync('git', ['diff', '--exit-code', '--stat', '--', target], { cwd: root, stdio: 'inherit' })
const untracked = execFileSync('git', ['ls-files', '--others', '--exclude-standard', '--', target], { cwd: root, encoding: 'utf8' }).trim()

if (diff.status !== 0 || untracked !== '') {
  if (untracked !== '') console.error(`Unversionierte Dateien in ${target}:\n${untracked}`)
  console.error(`\nboard:check fehlgeschlagen: ${target} ist nicht aktuell. Bitte "pnpm board:build" ausführen und das Ergebnis einchecken.`)
  process.exit(1)
}
console.log(`board:check ok: ${target} ist aktuell.`)
