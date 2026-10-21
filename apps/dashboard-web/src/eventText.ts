import { fmtDuration } from './format'
import { labelOf } from './labels'
import type { SakEvent } from './types'

export function eventTypeLabel(type: string): string {
  return type === 'diag.hook' ? labelOf('diag_event_type', type) : labelOf('event_type', type)
}

/** Kurzbeschreibung eines Events aus seinen Metadaten (Event-Log, Spec 007 User Story 3). */
export function describeEvent(event: SakEvent): string {
  const d = event.data as Record<string, unknown>
  const parts: string[] = []
  if (typeof d.round === 'number') parts.push(`Runde ${d.round}`)
  if (typeof d.role === 'string') parts.push(labelOf('role', d.role))
  if (typeof d.agent === 'string') parts.push(d.agent)
  if (typeof d.model === 'string') parts.push(d.model)
  if (typeof d.duration_s === 'number') parts.push(fmtDuration(d.duration_s))
  if (typeof d.verdict === 'string') parts.push(labelOf('verdict', d.verdict))
  if (typeof d.must_count === 'number') parts.push(`Muss ${d.must_count}`)
  if (typeof d.may_count === 'number') parts.push(`Kann ${d.may_count}`)
  if (typeof d.gate === 'string') parts.push(labelOf('gate', d.gate))
  if (typeof d.kind === 'string') parts.push(labelOf('run_kind', d.kind))
  if (typeof d.max_rounds === 'number') parts.push(`max. ${d.max_rounds} Runden`)
  if (typeof d.base_branch === 'string') parts.push(`Basis ${d.base_branch}`)
  if (typeof d.previous_state === 'string') parts.push(`vorher: ${labelOf('run_state', d.previous_state)}`)
  if (typeof d.merge_commit === 'string') parts.push(`Commit ${d.merge_commit.slice(0, 8)}`)
  if (event.type === 'run.pushed') {
    if (typeof d.remote === 'string' && typeof d.branch === 'string') parts.push(`${d.remote}/${d.branch}`)
    if (typeof d.commit === 'string') parts.push(`Commit ${d.commit.slice(0, 8)}`)
  }
  if (typeof d.phase === 'string') parts.push(labelOf('hook_phase', d.phase))
  if (Array.isArray(d.keys)) parts.push(`${d.keys.length} Schlüssel`)
  if (typeof d.reason === 'string') parts.push(d.reason)
  return parts.join(' · ')
}
