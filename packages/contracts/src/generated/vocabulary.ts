// GENERIERT von scripts/gen-zod.mjs aus schema/. Nicht von Hand ändern.

export const vocabulary = {
  "version": 1,
  "levels": {
    "stage": [
      "specified",
      "clarified",
      "planned",
      "tasked",
      "implementing",
      "implemented",
      "deployed",
      "verified"
    ],
    "run_state": [
      "building",
      "reviewing",
      "approved",
      "escalated",
      "paused",
      "merged",
      "reviewed",
      "aborted"
    ],
    "run_kind": [
      "pipeline",
      "review_only",
      "manual"
    ],
    "verdict": [
      "approve",
      "changes_requested",
      "needs_human"
    ],
    "severity": [
      "must",
      "may"
    ],
    "attention_kind": [
      "escalation",
      "approval",
      "clarification",
      "blocker",
      "decision",
      "operator_task",
      "stale_run"
    ],
    "event_type": [
      "run.started",
      "round.started",
      "station.started",
      "station.finished",
      "verdict.recorded",
      "run.escalated",
      "run.released",
      "run.returned",
      "run.approved",
      "run.paused",
      "run.resumed",
      "run.merged",
      "run.pushed",
      "run.reviewed",
      "run.aborted",
      "run.taken_over"
    ],
    "diag_event_type": [
      "diag.hook"
    ],
    "role": [
      "builder",
      "code_review",
      "ui_review",
      "security_review",
      "docs",
      "integrator"
    ],
    "gate": [
      "start_approval",
      "protected_paths",
      "review_integrity",
      "round_limit",
      "release",
      "deploy_approval"
    ],
    "station_state": [
      "running",
      "finished"
    ],
    "run_source": [
      "local",
      "cloud"
    ],
    "marker_kind": [
      "deploy",
      "verified"
    ],
    "ticker_kind": [
      "commit",
      "deploy",
      "verified"
    ],
    "board_source": [
      "live",
      "snapshot"
    ],
    "hook_phase": [
      "start",
      "stop"
    ],
    "agent_environment": [
      "claude",
      "copilot"
    ]
  }
} as const

export type Stage = (typeof vocabulary.levels.stage)[number]
export type RunState = (typeof vocabulary.levels.run_state)[number]
export type RunKind = (typeof vocabulary.levels.run_kind)[number]
export type Verdict = (typeof vocabulary.levels.verdict)[number]
export type Severity = (typeof vocabulary.levels.severity)[number]
export type AttentionKind = (typeof vocabulary.levels.attention_kind)[number]
export type EventType = (typeof vocabulary.levels.event_type)[number]
export type DiagEventType = (typeof vocabulary.levels.diag_event_type)[number]
export type Role = (typeof vocabulary.levels.role)[number]
export type Gate = (typeof vocabulary.levels.gate)[number]
export type StationState = (typeof vocabulary.levels.station_state)[number]
export type RunSource = (typeof vocabulary.levels.run_source)[number]
export type MarkerKind = (typeof vocabulary.levels.marker_kind)[number]
export type TickerKind = (typeof vocabulary.levels.ticker_kind)[number]
export type BoardSource = (typeof vocabulary.levels.board_source)[number]
export type HookPhase = (typeof vocabulary.levels.hook_phase)[number]
export type AgentEnvironment = (typeof vocabulary.levels.agent_environment)[number]

export type VocabularyLevel = keyof typeof vocabulary.levels
