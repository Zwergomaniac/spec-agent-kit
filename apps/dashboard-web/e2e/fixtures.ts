import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import type { Board, SakEvent } from '@sak/contracts'

export const BASE_URL = 'http://127.0.0.1:3100'
export const ADMIN_PASSWORD = 'e2e-test-passwort-123'
export const SESSION_SECRET = 'e2e-session-secret-e2e-session-secret-0123'

export const PILOT_KEY = 'immo-agent'
export const PILOT_RUN = '088-20261019-101500'
export const SECOND_KEY = 'spec-agent-kit'

export function pilotBoard(): Board {
  const url = new URL('../../../packages/contracts/examples/valid/board-pilot-immo-agent.json', import.meta.url)
  return JSON.parse(readFileSync(fileURLToPath(url), 'utf8')) as Board
}

/** Leitet aus den Läufen des Pilot-Boards eine Event-Folge ab (Start, Runden, Stationen, Urteile, Eskalation). */
export function pilotEvents(board: Board): SakEvent[] {
  const events: SakEvent[] = []
  let n = 0
  const push = (runId: string, spec: string, type: string, ts: string, data: unknown): void => {
    n += 1
    events.push({
      schema: 'sak.event/1',
      event_id: `01K8M3Q7R5${String(n).padStart(16, '0')}`,
      type,
      ts,
      project: board.project.key,
      run_id: runId,
      spec,
      data
    } as SakEvent)
  }
  for (const run of board.runs) {
    push(run.run_id, run.spec, 'run.started', run.started_at, {
      kind: run.kind,
      base_branch: 'main',
      base_commit: 'a1b2c3d4e5f60718293a4b5c6d7e8f9012345678',
      max_rounds: run.max_rounds
    })
    let lastRound = 0
    for (const s of run.stations) {
      if (s.round !== lastRound) {
        push(run.run_id, run.spec, 'round.started', s.started_at, { round: s.round })
        lastRound = s.round
      }
      push(run.run_id, run.spec, 'station.started', s.started_at, { round: s.round, role: s.role, agent: s.agent })
      const end = new Date(Date.parse(s.started_at) + (s.duration_s ?? 0) * 1000).toISOString()
      if (s.state === 'finished') push(run.run_id, run.spec, 'station.finished', end, { round: s.round, role: s.role, agent: s.agent, duration_s: s.duration_s ?? 0 })
      if (s.verdict) push(run.run_id, run.spec, 'verdict.recorded', end, { round: s.round, role: s.role, verdict: s.verdict, must_count: s.must_count ?? 0, may_count: s.may_count ?? 0 })
    }
    for (const e of run.escalations) push(run.run_id, run.spec, 'run.escalated', e.ts, { round: e.round, gate: e.gate, reason: e.reason })
    if (run.state === 'paused') push(run.run_id, run.spec, 'run.paused', run.updated_at, { reason: 'Betreiber hat pausiert' })
    if (run.state === 'merged') push(run.run_id, run.spec, 'run.merged', run.updated_at, {})
  }
  return events
}

export function secondBoard(base: Board): Board {
  return {
    ...base,
    project: { key: SECOND_KEY, name: 'Spec Agent Kit', base_branch: 'main' },
    metrics: { in_progress: 1, done: 6, blocked: 0, waiting: 0, mean_lead_time_days: 2.1 },
    specs: base.specs.slice(0, 3),
    attention: [],
    runs: [],
    markers: [],
    ticker: [],
    notes: []
  }
}

/** Weitere Projekte, damit das Portfolio-Raster auf breiten Fenstern mehrere Karten je Zeile zeigt. */
export const EXTRA_PROJECTS = [
  { key: 'ai-forge', name: 'AI Forge', specs: 8 },
  { key: 'kundenportal', name: 'Kundenportal', specs: 5 },
  { key: 'specboard', name: 'Specboard', specs: 10 },
  { key: 'docs-hub', name: 'Docs Hub', specs: 6 },
  { key: 'infra-tools', name: 'Infra Tools', specs: 9 }
] as const

export function extraBoard(base: Board, key: string, name: string, specs: number): Board {
  return {
    ...base,
    project: { key, name, base_branch: 'main' },
    metrics: { ...base.metrics, in_progress: 2, done: specs - 3, blocked: 0 },
    specs: base.specs.filter((s) => !s.descoped).slice(0, specs),
    attention: base.attention.slice(0, 1),
    runs: [],
    ticker: [],
    notes: []
  }
}

// ---------------------------------------------------------------------------
// Großes Projekt: etwa 90 Specs über alle Stationen, 19 Aufmerksamkeitseinträge, sehr lange Titel
// und Slugs (mindestens 40 Zeichen ohne Leerzeichen) und mehrere Läufe. Testet das Board-Layout.
// ---------------------------------------------------------------------------
export const LARGE_KEY = 'immoagent'
export const LARGE_NAME = 'ImmoAgent Großprojekt'
export const LARGE_RUN = '090-20261020-090000'

const LARGE_STAGES: Array<[string, number]> = [
  ['specified', 6],
  ['clarified', 5],
  ['planned', 6],
  ['tasked', 9],
  ['implementing', 4],
  ['implemented', 9],
  ['deployed', 7],
  ['verified', 45]
]

const SLUG_WORDS = [
  'search-templates-placeholders',
  'postleitzahl-mittelpunkt-ungefaehre-lage',
  'expose-export-pdf-vorlagen-verwaltung',
  'kartenlayer-clustering-performance',
  'benachrichtigungen-digest-zeitplan',
  'mandantenfaehige-rollen-und-rechte',
  'objektbewertung-vergleichswerte-import',
  'besichtigungstermine-kalender-sync'
]

export function largeBoard(base: Board): Board {
  const now = Date.now()
  const iso = (daysAgo: number): string => new Date(now - daysAgo * 86_400_000).toISOString()
  const specs: Board['specs'] = []
  let n = 0
  for (const [stage, count] of LARGE_STAGES) {
    for (let i = 0; i < count; i++) {
      n += 1
      const word = SLUG_WORDS[(n * 3) % SLUG_WORDS.length]!
      // Jede zweite Spec bekommt einen noch längeren Slug; alle Wortketten haben über 40 Zeichen ohne Leerzeichen.
      const slug = n % 2 === 0 ? `${word}-fuer-grosse-portfolios-${n}` : `${word}-${n}`
      const dir = `${String(n).padStart(3, '0')}-${slug}`
      const done = ['verified', 'deployed', 'implemented'].includes(stage) ? 14 : stage === 'implementing' ? 6 : 0
      const open = stage === 'implementing' ? 8 : stage === 'tasked' ? 12 : 0
      specs.push({
        number: n,
        dir,
        title:
          n % 3 === 0
            ? `Ungefähre_Lage_über_den_Postleitzahl-Mittelpunkt_darstellen_ohne_exakte_Adresse_preiszugeben_${n}`
            : `Ungefähre Lage über den Postleitzahl-Mittelpunkt für Spec ${n} darstellen und Suchvorlagen mit Platzhaltern verwalten`,
        descoped: false,
        blocked: stage === 'implementing' && i === 0,
        waiting: stage === 'tasked' && i < 4 ? 'approval' : stage === 'clarified' && i < 2 ? 'clarification' : null,
        tasks: { done, open },
        started_at: iso(40 - Math.min(n / 3, 39)),
        updated_at: iso(Math.min(n / 10, 9)),
        ...(stage === 'verified' ? { finished_at: iso(2 + (n % 20)), lead_time_days: 1.5 + (n % 7) } : {}),
        stage
      } as Board['specs'][number])
    }
  }
  for (const d of [1, 2, 3]) {
    n += 1
    specs.push({
      number: n,
      dir: `${String(n).padStart(3, '0')}-zurueckgestellt-altes-feature-mit-sehr-langem-slug-${d}`,
      title: `Zurückgestelltes Feature ${d}`,
      descoped: true,
      blocked: false,
      waiting: null,
      tasks: { done: 0, open: 3 },
      stage: null
    })
  }

  const pool = specs.filter((s) => s.stage === 'tasked' || s.stage === 'planned' || s.stage === 'clarified')
  const kinds = ['decision', 'escalation', 'blocker', 'operator_task', 'clarification', 'stale_run', 'approval'] as const
  const attention: Board['attention'] = []
  for (let i = 0; i < 19; i++) {
    const spec = pool[i % pool.length]!
    attention.push({
      kind: i < 12 ? 'approval' : kinds[i % kinds.length]!,
      spec: spec.dir,
      reason:
        i % 2 === 0
          ? 'Tasks fertig, wartet auf Freigabe zur Umsetzung'
          : `Offene Entscheidung zu ${spec.dir}: bitte Umfang, Reihenfolge und Abnahmekriterien bestätigen, bevor die Umsetzung startet`,
      source: `specs/${spec.dir}/tasks.md`
    })
  }

  const roles = ['builder', 'code_review', 'ui_review'] as const
  const states = ['escalated', 'merged', 'approved', 'reviewing', 'merged', 'aborted'] as const
  const runSpecs = [...specs.filter((s) => s.stage === 'implementing' || s.stage === 'implemented'), ...specs.filter((s) => s.stage === 'tasked').slice(0, 2)].slice(0, 6)
  const runs: Board['runs'] = runSpecs.map((s, idx) => {
    const started = new Date(now - (idx + 1) * 3 * 3_600_000)
    const day = started.toISOString().slice(0, 10).replaceAll('-', '')
    const runId = idx === 0 ? LARGE_RUN : `${String(s.number).padStart(3, '0')}-${day}-${100000 + idx * 1111}`
    const state = states[idx]!
    const at = (min: number): string => new Date(started.getTime() + min * 60_000).toISOString()
    return {
      run_id: runId,
      spec: s.dir,
      kind: 'pipeline',
      state,
      round: 2,
      max_rounds: 3,
      active: idx === 0,
      started_at: at(0),
      updated_at: at(70),
      last_event_at: at(70),
      idle: false,
      stale: false,
      origin: { machine: 'dev-laptop-mit-sehr-langem-rechnernamen', branch: 'feature/lange-branch-bezeichnung-ohne-leerzeichen', source: 'local' },
      stations: [1, 2].flatMap((round) =>
        roles.map((role, k) => ({
          round,
          role,
          agent: role === 'builder' ? 'pipeline-builder-mit-extrem-langem-agentennamen-ohne-leerzeichen' : `pipeline-${role}`,
          model: 'opus',
          state: 'finished' as const,
          started_at: at(round * 20 + k),
          duration_s: 300 + k * 60,
          ...(role === 'builder'
            ? {}
            : { verdict: round === 2 && role === 'code_review' ? ('changes_requested' as const) : ('approve' as const), must_count: round === 2 ? 1 : 0, may_count: 1 })
        }))
      ),
      escalations:
        state === 'escalated'
          ? [{ ts: at(70), round: 2, gate: 'round_limit' as const, reason: 'Rundenlimit erreicht, offene Muss-Befunde bei der Umsetzung der Postleitzahl-Mittelpunkt-Berechnung', open: true }]
          : []
    } as Board['runs'][number]
  })

  return {
    ...base,
    generated_at: new Date(now).toISOString(),
    project: { key: LARGE_KEY, name: LARGE_NAME, base_branch: 'main' },
    metrics: { in_progress: 13, done: 45, blocked: 1, waiting: 6, mean_lead_time_days: 4.2 },
    specs,
    attention,
    runs,
    markers: [{ kind: 'deploy', specs: [86, 87], ts: new Date(now - 86_400_000).toISOString(), commit: '0f1e2d3c4b5a69788796a5b4c3d2e1f001122334' }],
    ticker: base.ticker,
    notes: []
  }
}
