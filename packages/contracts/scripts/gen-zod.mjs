// Erzeugt aus schema/ die Dateien in src/generated/ (Zod-Schemas, Typen, Vokabular, Labels, Limits).
// Deterministisch: feste Reihenfolge (Abhängigkeitsordnung, sonst Reihenfolge der Quelle), keine Zeitstempel,
// LF-Zeilenenden. Die erzeugten Dateien werden eingecheckt; `pnpm contracts:check` prüft ihre Aktualität.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { jsonSchemaToZod } from 'json-schema-to-zod'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const schemaDir = path.join(root, 'schema')
const outDir = path.join(root, 'src', 'generated')

const readJson = (rel) => JSON.parse(fs.readFileSync(path.join(schemaDir, rel), 'utf8'))
const write = (name, text) => {
  fs.mkdirSync(outDir, { recursive: true })
  fs.writeFileSync(path.join(outDir, name), text, { encoding: 'utf8' })
}
const pascal = (s) => s.replace(/(^|[_.-])(\w)/g, (_, __, c) => c.toUpperCase())
const camel = (s) => {
  const p = pascal(s)
  return p[0].toLowerCase() + p.slice(1)
}
const HEADER = '// GENERIERT von scripts/gen-zod.mjs aus schema/. Nicht von Hand ändern.\n'

// ---------- Zod ----------
const FILES = ['common', 'event', 'board', 'ingest']
const schemas = Object.fromEntries(FILES.map((f) => [f, readJson(`${f}.schema.json`)]))

/** Bezeichner der Konstante für ein Def (common: ohne Präfix) oder das Top-Level-Schema. */
const defName = (file, def) => (file === 'common' ? `${camel(def)}Schema` : `${file}${pascal(def)}Schema`)
const topName = (file) => `${file}Schema`

function resolveRef(file, ref) {
  const [target, fragment] = ref.split('#')
  const targetFile = target ? target.replace('.schema.json', '') : file
  if (!fragment) return { file: targetFile, name: topName(targetFile), key: `${targetFile}:` }
  const m = /^\/\$defs\/(.+)$/.exec(fragment)
  if (!m) throw new Error(`Nicht unterstützte Referenz: ${ref}`)
  return { file: targetFile, name: defName(targetFile, m[1]), key: `${targetFile}:${m[1]}` }
}

function collectRefs(node, file, acc) {
  if (Array.isArray(node)) node.forEach((n) => collectRefs(n, file, acc))
  else if (node && typeof node === 'object') {
    for (const [k, v] of Object.entries(node)) {
      if (k === '$ref') acc.add(resolveRef(file, v).key)
      else collectRefs(v, file, acc)
    }
  }
  return acc
}

// Knoten: jedes Def und jedes Top-Level-Schema.
const nodes = new Map()
for (const file of FILES) {
  for (const [def, schema] of Object.entries(schemas[file].$defs ?? {})) {
    nodes.set(`${file}:${def}`, { file, name: defName(file, def), schema })
  }
  if (file !== 'common') {
    const { $defs, ...top } = schemas[file]
    nodes.set(`${file}:`, { file, name: topName(file), schema: top })
  }
}
const ordered = []
const state = new Map()
function visit(key) {
  if (state.get(key) === 'done') return
  if (state.get(key) === 'active') throw new Error(`Zyklische Referenz bei ${key}`)
  state.set(key, 'active')
  const node = nodes.get(key)
  if (!node) throw new Error(`Unbekannte Referenz ${key}`)
  for (const dep of collectRefs(node.schema, node.file, new Set())) visit(dep)
  state.set(key, 'done')
  ordered.push(node)
}
for (const key of nodes.keys()) visit(key)

let zodSource = `${HEADER}import { z } from 'zod'\n`
const typeExports = []
// json-schema-to-zod verdoppelt Backslashes in Mustern nicht; deshalb sind sie in den Schemas verboten
// (Zeichenklassen wie [.] statt \.).
const assertNoBackslashPatterns = (node, where) => {
  if (Array.isArray(node)) node.forEach((n) => assertNoBackslashPatterns(n, where))
  else if (node && typeof node === 'object') {
    if (typeof node.pattern === 'string' && node.pattern.includes(String.fromCharCode(92))) {
      throw new Error(`Muster mit Backslash in ${where}: ${node.pattern}`)
    }
    Object.values(node).forEach((n) => assertNoBackslashPatterns(n, where))
  }
}

for (const node of ordered) {
  assertNoBackslashPatterns(node.schema, node.name)
  const options = {
    module: 'none',
    noImport: true,
    zodVersion: 3,
    withoutDefaults: true,
    // Referenzen werden zu Bezeichnern bereits erzeugter Konstanten (relativ zur Quelldatei).
    parserOverride: (schema) => {
      if (typeof schema.$ref === 'string') return resolveRef(node.file, schema.$ref).name
    }
  }
  const expr = jsonSchemaToZod(node.schema, options)
  zodSource += `\nexport const ${node.name} = ${expr}\n`
  if (node.name.endsWith('Schema')) {
    typeExports.push(node.name)
  }
}

const TYPE_NAMES = {
  eventSchema: 'SakEvent',
  boardSchema: 'Board',
  ingestRequestSchema: 'IngestRequest',
  ingestResultSchema: 'IngestResult',
  ingestSchema: 'IngestDocument'
}
zodSource += '\n'
for (const [schemaName, typeName] of Object.entries(TYPE_NAMES)) {
  if (!typeExports.includes(schemaName)) throw new Error(`Schema ${schemaName} fehlt`)
  zodSource += `export type ${typeName} = z.infer<typeof ${schemaName}>\n`
}
write('zod.ts', zodSource)

// ---------- Vokabular, Labels, Limits ----------
const vocab = readJson('vocabulary.json')
const labelsDe = readJson('labels/de.json')
const limits = readJson('limits.json')

let vocabSource = `${HEADER}\nexport const vocabulary = ${JSON.stringify(vocab, null, 2)} as const\n\n`
for (const level of Object.keys(vocab.levels)) {
  vocabSource += `export type ${pascal(level)} = (typeof vocabulary.levels.${level})[number]\n`
}
vocabSource += `\nexport type VocabularyLevel = keyof typeof vocabulary.levels\n`
write('vocabulary.ts', vocabSource)

write(
  'labels.ts',
  `${HEADER}\nexport const labelsDe = ${JSON.stringify(labelsDe, null, 2)} as const\n\nexport const labels = { de: labelsDe } as const\n\nexport type Locale = keyof typeof labels\n`
)

const limitEntries = Object.entries(limits)
  .filter(([k]) => k !== 'version')
  .map(([k, v]) => `  ${k.toUpperCase()}: ${JSON.stringify(v)}`)
write('limits.ts', `${HEADER}\nexport const LIMITS = {\n${limitEntries.join(',\n')}\n} as const\n`)

console.log(`gen-zod: ${ordered.length} Schemas, ${Object.keys(vocab.levels).length} Vokabular-Ebenen`)
