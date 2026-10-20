import { label, vocabulary, type VocabularyLevel } from '@sak/contracts'
import type { BadgeVariant } from '@/components/ui/badge'

/**
 * Anzeigebezeichnung aus den Contracts (Locale de). Unbekannte Werte erscheinen als
 * "unbekannt (wert)" (Spec 007 FR-009), nie als roher Maschinenwert.
 */
export function labelOf(level: VocabularyLevel, value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '–'
  const known = (vocabulary.levels[level] as readonly string[]).includes(value)
  return known ? label(level, value) : `unbekannt (${value})`
}

const isKnown = (level: VocabularyLevel, value: string): boolean => (vocabulary.levels[level] as readonly string[]).includes(value)

/** Farbton je Laufzustand. Unbekannte Werte bleiben neutral. */
export function runStateTone(state: string): BadgeVariant {
  if (!isKnown('run_state', state)) return 'outline'
  switch (state) {
    case 'escalated':
      return 'danger'
    case 'paused':
      return 'warning'
    case 'building':
    case 'reviewing':
      return 'info'
    case 'approved':
    case 'merged':
    case 'reviewed':
      return 'success'
    default:
      return 'secondary'
  }
}

export function verdictTone(verdict: string): BadgeVariant {
  if (!isKnown('verdict', verdict)) return 'outline'
  return verdict === 'approve' ? 'success' : verdict === 'changes_requested' ? 'warning' : 'danger'
}

export function attentionTone(kind: string): BadgeVariant {
  if (!isKnown('attention_kind', kind)) return 'outline'
  switch (kind) {
    case 'escalation':
    case 'blocker':
    case 'stale_run':
      return 'danger'
    case 'approval':
    case 'decision':
    case 'operator_task':
      return 'warning'
    default:
      return 'info'
  }
}
