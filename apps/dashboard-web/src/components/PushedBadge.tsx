import { Badge } from '@/components/ui/badge'
import type { BoardRun } from '@/types'

/** Zusatz „gepusht“ am Lauf (Spec 012 FR-006): erscheint, sobald ein `run.pushed` vorliegt. */
export function PushedBadge({ run }: { run: Pick<BoardRun, 'pushed'> }) {
  if (!run.pushed) return null
  return (
    <Badge variant="outline" data-testid="pushed-badge">
      gepusht
    </Badge>
  )
}
