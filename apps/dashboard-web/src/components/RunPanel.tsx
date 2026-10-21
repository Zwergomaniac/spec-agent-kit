import { ArrowRight, Cpu, Radio } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fmtDuration, fmtRelative } from '@/format'
import { labelOf, runStateTone, verdictTone } from '@/labels'
import { links, safeLink } from '@/router'
import type { BoardRun, BoardSpec } from '@/types'
import { PushedBadge } from './PushedBadge'
import { EmptyState } from './states'

/** Agenten-Panel: Stationen der aktuellen Runde des aktiven Laufs. */
export function RunPanel({ projectKey, run, spec }: { projectKey: string; run: BoardRun | undefined; spec: BoardSpec | undefined }) {
  if (!run) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Radio className="size-4 text-muted-foreground" /> Agenten
          </CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState title="Kein aktiver Lauf" className="py-6">
            Sobald ein Lauf startet, erscheinen hier Rolle, Agent und Urteil je Station.
          </EmptyState>
        </CardContent>
      </Card>
    )
  }

  const stations = run.stations.filter((s) => s.round === run.round)
  const openEscalation = [...run.escalations].reverse().find((e) => e.open)

  return (
    <Card data-testid="run-panel">
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Radio className="size-4 text-muted-foreground" /> Agenten
          </CardTitle>
          <a
            href={safeLink(() => links.run(projectKey, run.run_id))}
            className="inline-flex items-center gap-1 text-xs font-medium underline-offset-2 hover:underline"
          >
            Lauf-Details <ArrowRight className="size-3" />
          </a>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge variant={runStateTone(run.state)}>{labelOf('run_state', run.state)}</Badge>
          <PushedBadge run={run} />
          <span className="min-w-0 font-medium [overflow-wrap:anywhere]">{spec?.title ?? run.spec}</span>
          <span className="text-xs text-muted-foreground">
            Runde {run.round} von {run.max_rounds}
          </span>
        </div>
        {run.origin ? (
          <p className="text-xs text-muted-foreground">
            {[run.origin.source ? labelOf('run_source', run.origin.source) : null, run.origin.machine, run.origin.branch].filter(Boolean).join(' · ')}
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="grid gap-3">
        {openEscalation ? (
          <Alert variant="destructive">
            <AlertTitle>{openEscalation.gate ? labelOf('gate', openEscalation.gate) : labelOf('run_state', 'escalated')}</AlertTitle>
            <AlertDescription className="[overflow-wrap:anywhere]">{openEscalation.reason}</AlertDescription>
          </Alert>
        ) : null}

        {stations.length === 0 ? (
          <p className="text-sm text-muted-foreground">In dieser Runde ist noch keine Station gestartet.</p>
        ) : (
          <ol className="grid gap-2">
            {stations.map((s, i) => (
              <li key={`${s.role}-${s.started_at}-${i}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border bg-background/60 p-2.5 text-sm">
                <span className="inline-flex min-w-0 items-center gap-2">
                  <Cpu className="size-4 shrink-0 text-muted-foreground" />
                  <span className="font-medium">{labelOf('role', s.role)}</span>
                </span>
                <span className="min-w-0 font-mono text-xs text-muted-foreground [overflow-wrap:anywhere]">{s.agent}</span>
                {s.model ? <Badge variant="outline">{s.model}</Badge> : null}
                <span className="ml-auto flex items-center gap-2">
                  {s.state === 'running' ? (
                    <Badge variant="info">{labelOf('station_state', 'running')}</Badge>
                  ) : s.verdict ? (
                    <Badge variant={verdictTone(s.verdict)}>{labelOf('verdict', s.verdict)}</Badge>
                  ) : (
                    <Badge variant="secondary">{labelOf('station_state', s.state)}</Badge>
                  )}
                </span>
                <span className="basis-full text-xs text-muted-foreground tabular-nums">
                  {s.state === 'finished' ? fmtDuration(s.duration_s) : `gestartet ${fmtRelative(s.started_at)}`}
                  {s.verdict ? ` · Muss ${s.must_count ?? 0} · Kann ${s.may_count ?? 0}` : ''}
                </span>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}
