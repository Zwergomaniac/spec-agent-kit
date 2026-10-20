// Kopiert schema/ byte-genau nach packages/engine/src/spec_agent_kit/schemas/.
// Dateien im Ziel, die in der Quelle nicht (mehr) existieren, werden entfernt.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export const SOURCE_DIR = path.join(root, 'schema')
export const TARGET_DIR = path.resolve(root, '..', 'engine', 'src', 'spec_agent_kit', 'schemas')

function listFiles(dir, base = dir) {
  if (!fs.existsSync(dir)) return []
  const result = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) result.push(...listFiles(full, base))
    else result.push(path.relative(base, full).split(path.sep).join('/'))
  }
  return result
}

export function syncPython() {
  const source = listFiles(SOURCE_DIR)
  for (const rel of listFiles(TARGET_DIR)) {
    if (!source.includes(rel)) fs.rmSync(path.join(TARGET_DIR, rel))
  }
  for (const rel of source) {
    const target = path.join(TARGET_DIR, rel)
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.copyFileSync(path.join(SOURCE_DIR, rel), target)
  }
  return source.length
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(`sync-python: ${syncPython()} Dateien nach ${path.relative(process.cwd(), TARGET_DIR)}`)
}
