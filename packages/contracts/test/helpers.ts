import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import Ajv2020 from 'ajv/dist/2020.js'
import addFormats from 'ajv-formats'

const here = path.dirname(fileURLToPath(import.meta.url))
export const schemaDir = path.resolve(here, '..', 'schema')
export const examplesDir = path.resolve(here, '..', 'examples')
export const SCHEMA_ID_BASE = 'https://spec-agent-kit.local/schema/v1/'

export const SCHEMA_FILES = ['common', 'event', 'board', 'ingest', 'config'] as const
export type SchemaName = 'event' | 'board' | 'ingest' | 'config'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function readJson(file: string): any {
  return JSON.parse(fs.readFileSync(file, 'utf8'))
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const schemas: Record<(typeof SCHEMA_FILES)[number], any> = Object.fromEntries(
  SCHEMA_FILES.map((f) => [f, readJson(path.join(schemaDir, `${f}.schema.json`))])
) as never

export function createAjv(): Ajv2020 {
  const ajv = new Ajv2020({ strict: true })
  ;(addFormats as unknown as (a: Ajv2020) => void)(ajv)
  ajv.addKeyword('x-vocab')
  ajv.addKeyword('x-vocab-subset')
  for (const f of SCHEMA_FILES) ajv.addSchema(schemas[f])
  return ajv
}

export interface Example {
  file: string
  valid: boolean
  schema: SchemaName
  data: unknown
}

export function loadExamples(): Example[] {
  const result: Example[] = []
  for (const dir of ['valid', 'invalid'] as const) {
    for (const file of fs.readdirSync(path.join(examplesDir, dir)).sort()) {
      if (!file.endsWith('.json')) continue
      const prefix = file.split('-')[0] as SchemaName
      result.push({
        file: `${dir}/${file}`,
        valid: dir === 'valid',
        schema: prefix,
        data: readJson(path.join(examplesDir, dir, file))
      })
    }
  }
  return result
}

/** Alle Knoten eines JSON-Dokuments (Tiefensuche, stabile Reihenfolge). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function* walk(node: any, pointer = ''): Generator<[string, any]> {
  yield [pointer, node]
  if (Array.isArray(node)) {
    for (let i = 0; i < node.length; i++) yield* walk(node[i], `${pointer}/${i}`)
  } else if (node && typeof node === 'object') {
    for (const [k, v] of Object.entries(node)) yield* walk(v, `${pointer}/${k}`)
  }
}
