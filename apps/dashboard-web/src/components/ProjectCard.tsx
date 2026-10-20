import { AlertTriangle, ArrowRight, BellRing, Clock, Cpu, Layers, WifiOff } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fmtRelative, fmtDateTime } from '@/format'
import { labelOf, runStateTone } from '@/labels'
import { links, safeLink } from '@/router'
import type { PortfolioProject, PortfolioWarning } from '@/types'
import { cn } from '@/lib/utils'

const WARNING_TEXT: Record<PortfolioWarning, string> = {
  stale: labelOf('attention_kind', 'stale_run'),
  idle: 'Lauf inaktiv',
  no_push_24h: 'Kein Push seit über 24 Std.'
}

export function ProjectCard({ project, now }: { project: PortfolioProject; now?: number }) {
  const escalated = project.escalation !== null
  const run = project.active_run
  const projectHref = safeLink(() => links.project(project.key))

  return (
    <Card className={cn('gap-4', escalated && 'border-danger/60 bg-danger-soft/40')} data-testid={`project-card-${project.key}`} data-escalated={escalated}>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <CardTitle className="truncate text-lg">
            <a href={projectHref} className="hover:underline focus-visible:underline">
              {project.name}
            </a>
          </CardTitle>
          <p className="font-mono text-xs text-muted-foreground">{project.key}</p>
        </div>
        {escalated ? (
          <Badge variant="danger">
            <AlertTriangle /> {labelOf('run_state', 'escalated')}
          </Badge>
        ) : null}
      </CardHeader>

      <CardContent className="grid gap-4">
        {escalated && project.escalation ? (
          <div className="rounded-lg border border-danger/40 bg-card/60 p-3 text-sm">
            <p className="font-medium text-danger">{project.escalation.reason ?? 'Eskalation ohne Angabe eines Grundes'}</p>
            <a
              href={safeLink(() => links.run(project.key, project.escalation!.run_id))}
              className="mt-1 inline-flex items-center gap-1 text-xs font-medium underline-offset-2 hover:underline"
            >
              Lauf {project.escalation.run_id} öffnen <ArrowRight className="size-3" />
            </a>
          </div>
        ) : null}

        {!project.has_board ? (
          <p className="text-sm text-muted-foreground">Noch keine Daten. Das Projekt hat bisher kein Board eingeliefert.</p>
        ) : run ? (
          <div className="grid gap-1.5 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={runStateTone(run.state)}>{labelOf('run_state', run.state)}</Badge>
              <span className="font-medium">{run.spec}</span>
            </div>
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span>
                Runde {run.round} von {run.max_rounds}
              </span>
              {run.current_station ? (
                <span className="inline-flex items-center gap-1">
                  <Cpu className="size-3" />
                  {labelOf('role', run.current_station.role)}
                  <span className="font-mono">{run.current_station.agent}</span>
                </span>
              ) : null}
              <a href={safeLink(() => links.run(project.key, run.run_id))} className="font-medium text-foreground underline-offset-2 hover:underline">
                Lauf ansehen
              </a>
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Kein aktiver Lauf.</p>
        )}

        {project.has_board ? (
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="flex items-center gap-1 text-xs text-muted-foreground">
                <BellRing className="size-3" /> Aufmerksamkeit
              </dt>
              <dd className={cn('text-xl font-semibold tabular-nums', project.attention_count > 0 && 'text-warning')}>{project.attention_count}</dd>
            </div>
            <div>
              <dt className="flex items-center gap-1 text-xs text-muted-foreground">
                <Layers className="size-3" /> Specs in Arbeit
              </dt>
              <dd className="text-xl font-semibold tabular-nums">{project.in_progress}</dd>
            </div>
          </dl>
        ) : null}

        {project.warnings.length > 0 ? (
          <ul className="flex flex-wrap gap-1.5" aria-label="Warnungen">
            {project.warnings.map((w) => (
              <li key={w}>
                <Badge variant="warning">
                  {w === 'no_push_24h' ? <WifiOff /> : <Clock />}
                  {WARNING_TEXT[w]}
                </Badge>
              </li>
            ))}
          </ul>
        ) : null}

        <p className="text-xs text-muted-foreground" title={fmtDateTime(project.last_activity)}>
          Letzte Aktivität: {fmtRelative(project.last_activity, now)}
        </p>
      </CardContent>
    </Card>
  )
}
