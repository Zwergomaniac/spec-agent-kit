import { Lock, UserRound } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { fmtDays, fmtRelative, specNumber } from '@/format'
import { labelOf } from '@/labels'
import { links, safeLink } from '@/router'
import type { BoardRun, BoardSpec } from '@/types'

export function SpecCard({ spec, projectKey, run }: { spec: BoardSpec; projectKey: string; run?: BoardRun }) {
  const total = spec.tasks.done + spec.tasks.open
  const pct = total === 0 ? 0 : Math.round((spec.tasks.done / total) * 100)

  return (
    <li className="min-w-0 rounded-lg border bg-card p-2.5 min-[1536px]:p-3 text-sm shadow-xs" data-testid={`spec-${spec.number}`}>
      <div className="flex flex-col gap-0.5 min-[1536px]:flex-row min-[1536px]:items-start min-[1536px]:gap-2">
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{specNumber(spec.number)}</span>
        <span className="min-w-0 flex-1 font-medium leading-snug break-words">{spec.title}</span>
      </div>

      {total > 0 ? (
        <div className="mt-2.5">
          <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`Tasks: ${spec.tasks.done} von ${total} erledigt`}>
            <div className="h-full rounded-full bg-success" style={{ width: `${pct}%` }} />
          </div>
          <p className="mt-1 text-xs text-muted-foreground tabular-nums">
            {spec.tasks.done} von {total} Tasks
          </p>
        </div>
      ) : null}

      {spec.waiting || spec.blocked ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {spec.waiting ? (
            <Badge variant="warning" className="max-w-full shrink whitespace-normal text-left">
              <UserRound /> Wartet: {labelOf('attention_kind', spec.waiting)}
            </Badge>
          ) : null}
          {spec.blocked ? (
            <Badge variant="danger" className="max-w-full shrink whitespace-normal text-left">
              <Lock /> {labelOf('attention_kind', 'blocker')}
            </Badge>
          ) : null}
        </div>
      ) : null}

      <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        {spec.lead_time_days !== undefined ? <span>Durchlauf {fmtDays(spec.lead_time_days)}</span> : null}
        {spec.updated_at ? <span>aktualisiert {fmtRelative(spec.updated_at)}</span> : null}
        {run ? (
          <a href={safeLink(() => links.run(projectKey, run.run_id))} className="font-medium text-foreground underline-offset-2 hover:underline">
            Lauf {labelOf('run_state', run.state)}
          </a>
        ) : null}
      </p>
    </li>
  )
}
