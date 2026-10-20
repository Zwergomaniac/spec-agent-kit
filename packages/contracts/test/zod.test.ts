import { describe, expect, it } from 'vitest'
import { boardSchema, eventSchema, ingestSchema, label } from '../src/index'
import { SCHEMA_ID_BASE, createAjv, loadExamples } from './helpers'

const ajv = createAjv()
const zodSchemas = { event: eventSchema, board: boardSchema, ingest: ingestSchema } as const
const examples = loadExamples()

describe('Zod beurteilt die Beispiele wie ajv (Spec 002 SC-001)', () => {
  it.each(examples.map((e) => [e.file, e] as const))('%s', (_file, example) => {
    const validate = ajv.getSchema(`${SCHEMA_ID_BASE}${example.schema}.schema.json`)
    const ajvOk = validate?.(example.data) === true
    const zodOk = zodSchemas[example.schema].safeParse(example.data).success
    expect(zodOk).toBe(ajvOk)
    expect(zodOk).toBe(example.valid)
  })

  it('lehnt unbekannte Felder ab, auch in data', () => {
    const base = examples.find((e) => e.file === 'valid/event-run-started.json')?.data as Record<string, unknown>
    expect(eventSchema.safeParse({ ...base, extra: 1 }).success).toBe(false)
    expect(eventSchema.safeParse({ ...base, data: { ...(base.data as object), prompt: 'x' } }).success).toBe(false)
  })
})

describe('label()', () => {
  it('liefert deutsche Bezeichnungen und gibt unbekannte Werte unverändert zurück', () => {
    expect(label('run_state', 'escalated')).toBe('Eskaliert')
    expect(label('verdict', 'needs_human', 'de')).toBe('Mensch prüft')
    expect(label('stage', 'unbekannt')).toBe('unbekannt')
  })
})
