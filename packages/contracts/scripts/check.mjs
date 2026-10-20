// contracts:check = Generieren + Synchronisieren + git diff --exit-code auf die generierten Pfade.
// Zusätzlich werden unversionierte generierte Dateien gemeldet (git diff sieht sie nicht).
import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repo = path.resolve(root, '..', '..')
const generated = ['packages/contracts/src/generated', 'packages/engine/src/spec_agent_kit/schemas']

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { cwd: repo, encoding: 'utf8', ...opts })
  if (r.error) throw r.error
  return r
}

for (const script of ['gen-zod.mjs', 'sync-python.mjs']) {
  const r = run(process.execPath, [path.join(root, 'scripts', script)], { stdio: 'inherit' })
  if (r.status !== 0) process.exit(r.status ?? 1)
}

const diff = run('git', ['diff', '--exit-code', '--stat', '--', ...generated])
const untracked = run('git', ['ls-files', '--others', '--exclude-standard', '--', ...generated])
if (diff.status !== 0 || untracked.stdout.trim() !== '') {
  console.error('contracts:check FEHLGESCHLAGEN: generierte Dateien sind nicht aktuell oder nicht eingecheckt.')
  if (diff.stdout) console.error(diff.stdout)
  if (untracked.stdout.trim()) console.error(`Unversioniert:\n${untracked.stdout}`)
  console.error('Bitte `pnpm contracts:gen` ausführen und das Ergebnis einchecken (git add).')
  process.exit(1)
}
console.log('contracts:check: generierte Dateien sind aktuell.')
