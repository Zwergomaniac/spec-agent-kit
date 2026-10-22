import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { LIMITS, labelsDe, vocabulary } from '../src/index'
import { SCHEMA_ID_BASE, createAjv, examplesDir, loadExamples, readJson, schemaDir, schemas, walk } from './helpers'

const ajv = createAjv()
const levels = vocabulary.levels as Record<string, readonly string[]>
const lvl = (name: string): readonly string[] => levels[name] ?? []

describe('Vokabular', () => {
  it('hat nur ASCII-Maschinenwerte in lower_snake_case (Ereignisarten mit Punkt)', () => {
    for (const [level, values] of Object.entries(levels)) {
      expect(values.length, level).toBeGreaterThan(0)
      expect(new Set(values).size, `${level}: doppelte Werte`).toBe(values.length)
      for (const v of values) expect(v, `${level}.${v}`).toMatch(/^[a-z][a-z_]*(?:\.[a-z_]+)?$/)
    }
  })

  it('ordnet jeden Wert genau einer Ebene zu (Spec 001 FR-002, SC-002)', () => {
    // marker_kind und ticker_kind sind Teilmengen-Ebenen der Board-Listen aus Spec 002 FR-006 und
    // wiederholen bewusst deploy/verified; sie sind von der Eindeutigkeitsprüfung ausgenommen.
    const exempt = new Set(['marker_kind', 'ticker_kind'])
    const seen = new Map<string, string>()
    for (const [level, values] of Object.entries(levels)) {
      if (exempt.has(level)) continue
      for (const v of values) {
        expect(seen.get(v), `${v} in ${seen.get(v)} und ${level}`).toBeUndefined()
        seen.set(v, level)
      }
    }
  })

  it('hat zu jedem Wert ein deutsches Label und keine überzähligen Labels (Spec 002 FR-002)', () => {
    const labels = labelsDe as Record<string, Record<string, string>>
    expect(Object.keys(labels).sort()).toEqual(Object.keys(levels).sort())
    for (const [level, values] of Object.entries(levels)) {
      const table = labels[level] ?? {}
      expect(Object.keys(table).sort(), level).toEqual([...values].sort())
      for (const v of values) expect((table[v] ?? '').trim().length, `${level}.${v}`).toBeGreaterThan(0)
    }
  })

  it('stimmt mit den Tabellen aus Spec 001 überein (Stichproben der Labels)', () => {
    expect(labelsDe.verdict).toEqual({ approve: 'OK', changes_requested: 'Änderung', needs_human: 'Mensch prüft' })
    expect(labelsDe.run_state.escalated).toBe('Eskaliert')
    expect(labelsDe.stage.implemented).toBe('Umsetzung fertig')
    expect(labelsDe.stage.verified).toBe('Live geprüft')
  })
})

describe('Enum und Vokabular (Spec 002 FR-002)', () => {
  it('jedes Enum in den Schemas verweist per x-vocab auf eine Ebene und stimmt mit ihr überein', () => {
    let count = 0
    for (const [name, schema] of Object.entries(schemas)) {
      for (const [pointer, node] of walk(schema)) {
        if (!node || typeof node !== 'object' || !Array.isArray(node.enum)) continue
        count++
        const where = `${name}${pointer}`
        const level = node['x-vocab'] as string | undefined
        expect(level, `${where}: x-vocab fehlt`).toBeTypeOf('string')
        const values = lvl(level ?? '')
        expect(values.length, `${where}: Ebene ${level} unbekannt`).toBeGreaterThan(0)
        if (node['x-vocab-subset'] === true) {
          for (const v of node.enum) expect(values, `${where}: ${v}`).toContain(v)
        } else {
          expect([...node.enum].sort(), where).toEqual([...values].sort())
        }
      }
    }
    expect(count).toBeGreaterThan(10)
  })

  it('die Rollen der Projektkonfiguration entsprechen der Ebene role (Spec 004 FR-002)', () => {
    const roles = schemas.config.properties.pipeline.properties.roles
    expect(Object.keys(roles.properties).sort()).toEqual([...lvl('role')].sort())
    expect(roles.additionalProperties).toBe(false)
  })

  it('die Event-Zweige decken genau event_type und diag_event_type ab', () => {
    const covered: string[] = []
    for (const branch of schemas.event.anyOf) {
      const t = branch.properties.type
      covered.push(...(t.const !== undefined ? [t.const] : t.enum))
    }
    expect([...covered].sort()).toEqual([...lvl('event_type'), ...lvl('diag_event_type')].sort())
    expect(new Set(covered).size).toBe(covered.length)
  })
})

describe('Limits', () => {
  it('stimmen mit den Schemas überein', () => {
    expect(schemas.board.properties.runs.maxItems).toBe(LIMITS.RUNS_MAX)
    expect(schemas.board.properties.ticker.maxItems).toBe(LIMITS.TICKER_MAX)
    expect(schemas.board.properties.notes.maxItems).toBe(LIMITS.NOTES_MAX)
    expect(schemas.ingest.$defs.request.properties.events.maxItems).toBe(LIMITS.INGEST_MAX_EVENTS)
    expect(schemas.common.$defs.reason.maxLength).toBe(LIMITS.REASON_MAX_CHARS)
    expect(schemas.common.$defs.name.maxLength).toBe(LIMITS.ORIGIN_FIELD_MAX_CHARS)
  })

  it('haben die Werte aus Spec 002', () => {
    expect(LIMITS.EVENT_MAX_BYTES).toBe(8 * 1024)
    expect(LIMITS.BOARD_MAX_BYTES).toBe(512 * 1024)
    expect(LIMITS.INGEST_MAX_BYTES).toBe(2 * 1024 * 1024)
    expect(LIMITS.INGEST_MAX_EVENTS).toBe(500)
    expect(readJson(path.join(schemaDir, 'limits.json')).event_max_bytes).toBe(8192)
  })
})

describe('Beispiele gegen ajv', () => {
  const examples = loadExamples()

  it('es gibt gültige und ungültige Beispiele je Schema', () => {
    for (const s of ['event', 'board', 'ingest', 'config', 'lock'] as const) {
      expect(examples.filter((e) => e.schema === s && e.valid).length, `${s} gültig`).toBeGreaterThan(0)
      expect(examples.filter((e) => e.schema === s && !e.valid).length, `${s} ungültig`).toBeGreaterThan(0)
    }
    expect(examplesDir).toBeTruthy()
  })

  it('es gibt ein gültiges Beispiel je Ereignisart (Spec 001 FR-022 und diag.hook)', () => {
    const types = new Set(
      examples.filter((e) => e.valid && e.schema === 'event').map((e) => (e.data as { type: string }).type)
    )
    for (const t of [...lvl('event_type'), ...lvl('diag_event_type')]) expect(types.has(t), t).toBe(true)
  })

  it.each(examples.map((e) => [e.file, e] as const))('%s', (_file, example) => {
    const validate = ajv.getSchema(`${SCHEMA_ID_BASE}${example.schema}.schema.json`)
    expect(validate).toBeDefined()
    const ok = validate?.(example.data)
    expect(ok, JSON.stringify(validate?.errors?.slice(0, 2))).toBe(example.valid)
  })

  it('das Pilot-Board zeigt Lauf 066 gemergt, 084 pausiert, 088 eskaliert (FR-010)', () => {
    const board = examples.find((e) => e.file === 'valid/board-pilot-immo-agent.json')?.data as {
      runs: { run_id: string; state: string }[]
      specs: { stage: string | null }[]
    }
    const state = (prefix: string): string | undefined => board.runs.find((r) => r.run_id.startsWith(prefix))?.state
    expect([state('066'), state('084'), state('088')]).toEqual(['merged', 'paused', 'escalated'])
    const stages = new Set(board.specs.map((s) => s.stage))
    for (const stage of lvl('stage')) expect(stages.has(stage), stage).toBe(true)
  })
})

describe('Autonomie-Stufen (Spec 012)', () => {
  const validateConfig = ajv.getSchema(`${SCHEMA_ID_BASE}config.schema.json`)
  const base = { schema: 'sak.config/1', project: { key: 'demo', name: 'Demo' } }

  it('run.pushed hat das Label "Gepusht"', () => {
    const labels = labelsDe as Record<string, Record<string, string>>
    expect(labels.event_type?.['run.pushed']).toBe('Gepusht')
  })

  it('akzeptiert gültige und lehnt ungültige autonomy-Blöcke ab', () => {
    for (const autonomy of [{}, { push: 'after_merge', deploy: 'never', remote: 'upstream' }]) {
      expect(validateConfig?.({ ...base, autonomy }), JSON.stringify(autonomy)).toBe(true)
    }
    for (const autonomy of [{ push: 'always' }, { deploy: 'auto' }, { remote: '' }, { force: true }]) {
      expect(validateConfig?.({ ...base, autonomy }), JSON.stringify(autonomy)).toBe(false)
    }
  })
})

describe('Dashboard-Auth (Spec 013)', () => {
  const validateConfig = ajv.getSchema(`${SCHEMA_ID_BASE}config.schema.json`)
  const base = { schema: 'sak.config/1', project: { key: 'demo', name: 'Demo' } }

  it('akzeptiert dashboard.auth key und proxy, lehnt anderes ab', () => {
    for (const auth of ['key', 'proxy']) {
      expect(validateConfig?.({ ...base, dashboard: { auth } }), auth).toBe(true)
    }
    for (const auth of ['token', '', 'Proxy', 1]) {
      expect(validateConfig?.({ ...base, dashboard: { auth } }), String(auth)).toBe(false)
    }
  })
})
