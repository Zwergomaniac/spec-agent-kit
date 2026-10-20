import type { Board, SakEvent } from '@sak/contracts'

export type { Board, SakEvent }
export type BoardSpec = Board['specs'][number]
export type BoardRun = Board['runs'][number]
export type BoardStation = BoardRun['stations'][number]
export type BoardAttention = Board['attention'][number]

// Antworten der Dashboard-API (nicht Teil der Contracts: sie beschreiben nur die Lese-API).
export type PortfolioWarning = 'stale' | 'idle' | 'no_push_24h'

export interface PortfolioProject {
  key: string
  name: string
  has_board: boolean
  board_generated_at: string | null
  last_ingest_at: string | null
  last_activity: string | null
  active_run: {
    run_id: string
    spec: string
    state: string
    round: number
    max_rounds: number
    current_station: { role: string; agent: string; state: string } | null
    idle: boolean
    stale: boolean
  } | null
  escalation: { run_id: string; spec: string; reason: string | null } | null
  attention_count: number
  in_progress: number
  /** Specs je Station (ohne zurückgestellte); alle Stationen des Vokabulars sind gesetzt. */
  stage_counts: Record<string, number>
  done: number
  attention_preview: Array<{ kind: string; spec: string | null }>
  attention_total: number
  last_marker: { kind: string; ts: string; specs: number[] } | null
  warnings: PortfolioWarning[]
}

export interface PortfolioResponse {
  generated_at: string
  projects: PortfolioProject[]
}

export interface ProjectResponse {
  project: { key: string; name: string }
  board: Board | null
  ingest: { last_ingest_at: string | null; board_received_at: string | null; event_count: number }
}

export interface RunResponse {
  project: string
  run: BoardRun | null
  events: SakEvent[]
}

export interface AdminProject {
  key: string
  name: string
  created_at: string
  last_ingest_at: string | null
}

export interface MetaResponse {
  kit_version: string
  vocabulary_version: number
}
