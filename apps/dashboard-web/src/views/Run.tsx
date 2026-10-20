import { ChevronRight, FileQuestion, Info } from 'lucide-react'
import { api, ApiError } from '@/api'
import { EmptyState, ErrorState, LastUpdated, LoadingView, PageHeader } from '@/components/states'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { eventTypeLabel, describeEvent } from '@/eventText'
import { fmtDateTime, fmtDuration } from '@/format'
import { usePolled } from '@/hooks'
import { labelOf, runStateTone, verdictTone } from '@/labels'
import { links, safeLink } from '@/router'
import type { BoardRun, BoardStation, SakEvent } from '@/types'

function groupByRound(stations: BoardStation[]): Array<[number, BoardStation[]]> {
  const map = new Map<number, BoardStation[]>()
  for (const s of stations) map.set(s.round, [...(map.get(s.round) ?? []), s])
  return [...map.entries()].sort((a, b) => a[0] - b[0])
}

function RoundCard({ round, stations }: { round: number; stations: BoardStation[] }) {
  return (
    <Card data-testid={`round-${round}`}>
      <CardHeader>
        <CardTitle className="text-base">Runde {round}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Rolle</TableHead>
              <TableHead>Agent</TableHead>
              <TableHead>Modell</TableHead>
              <TableHead>Gestartet</TableHead>
              <TableHead>Dauer</TableHead>
              <TableHead>Urteil</TableHead>
              <TableHead className="text-right">Muss</TableHead>
              <TableHead className="text-right">Kann</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {stations.map((s, i) => (
              <TableRow key={`${s.role}-${s.started_at}-${i}`}>
                <TableCell className="font-medium">{labelOf('role', s.role)}</TableCell>
                <TableCell className="font-mono text-xs [overflow-wrap:anywhere]">{s.agent}</TableCell>
                <TableCell className="text-muted-foreground">{s.model ?? '–'}</TableCell>
                <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(s.started_at)}</TableCell>
                <TableCell className="whitespace-nowrap tabular-nums">{s.state === 'running' ? labelOf('station_state', 'running') : fmtDuration(s.duration_s)}</TableCell>
                <TableCell>{s.verdict ? <Badge variant={verdictTone(s.verdict)}>{labelOf('verdict', s.verdict)}</Badge> : '–'}</TableCell>
                <TableCell className="text-right tabular-nums">{s.must_count ?? '–'}</TableCell>
                <TableCell className="text-right tabular-nums">{s.may_count ?? '–'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function Timeline({ events }: { events: SakEvent[] }) {
  const states = events.filter((e) => e.type.startsWith('run.'))
  if (states.length === 0) return <p className="text-sm text-muted-foreground">Keine Zustandsänderungen erfasst.</p>
  return (
    <ol className="relative ml-2 grid gap-4 border-l pl-5" data-testid="timeline">
      {states.map((e) => (
        <li key={e.event_id} className="relative text-sm">
          <span className="absolute top-1.5 -left-[1.6rem] size-2.5 rounded-full border-2 border-background bg-muted-foreground" aria-hidden />
          <p className="font-medium">{eventTypeLabel(e.type)}</p>
          <p className="text-xs text-muted-foreground">
            {fmtDateTime(e.ts)}
            {describeEvent(e) ? ` · ${describeEvent(e)}` : ''}
          </p>
        </li>
      ))}
    </ol>
  )
}

function EventLog({ events }: { events: SakEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-muted-foreground">Keine Events gespeichert (Aufbewahrung: 30 Tage).</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Zeit</TableHead>
          <TableHead>Ereignis</TableHead>
          <TableHead>Details</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {events.map((e) => (
          <TableRow key={e.event_id} data-testid="event-row">
            <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(e.ts)}</TableCell>
            <TableCell className="whitespace-nowrap font-medium">{eventTypeLabel(e.type)}</TableCell>
            <TableCell className="min-w-64 whitespace-normal text-muted-foreground">{describeEvent(e) || '–'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function RunSummary({ run }: { run: BoardRun }) {
  return (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <Badge variant={runStateTone(run.state)}>{labelOf('run_state', run.state)}</Badge>
      <span>{labelOf('run_kind', run.kind)}</span>
      <span>
        Runde {run.round} von {run.max_rounds}
      </span>
      {run.origin ? <span>{[run.origin.source ? labelOf('run_source', run.origin.source) : null, run.origin.machine, run.origin.branch].filter(Boolean).join(' · ')}</span> : null}
      <span>Start {fmtDateTime(run.started_at)}</span>
    </span>
  )
}

export function Run({ projectKey, runId }: { projectKey: string; runId: string }) {
  const { data, error, updatedAt, refresh } = usePolled(() => api.run(projectKey, runId), `run:${projectKey}:${runId}`)

  const crumbs = (
    <nav aria-label="Brotkrumen" className="mb-2 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
      <a href={links.portfolio()} className="hover:underline">
        Portfolio
      </a>
      <ChevronRight className="size-3" />
      <a href={safeLink(() => links.project(projectKey))} className="font-mono hover:underline">
        {projectKey}
      </a>
      <ChevronRight className="size-3" />
      <span className="font-mono [overflow-wrap:anywhere]">{runId}</span>
    </nav>
  )

  if (error instanceof ApiError && error.status === 404) {
    return (
      <>
        <PageHeader title="Lauf nicht gefunden">{crumbs}</PageHeader>
        <EmptyState title="Dieser Lauf ist nicht (mehr) bekannt" icon={<FileQuestion />}>
          Das Board enthält nur die letzten 20 Läufe, Events werden 30 Tage aufbewahrt.
        </EmptyState>
      </>
    )
  }
  if (!data) {
    return (
      <>
        <PageHeader title={runId}>{crumbs}</PageHeader>
        {error ? <ErrorState error={error} onRetry={refresh} /> : <LoadingView />}
      </>
    )
  }

  const { run, events } = data
  const rounds = run ? groupByRound(run.stations) : []

  return (
    <>
      <PageHeader
        title={run?.spec ?? runId}
        subtitle={run ? <RunSummary run={run} /> : <span className="font-mono">{runId}</span>}
        actions={<LastUpdated updatedAt={updatedAt} error={error} onRefresh={refresh} />}
      >
        {crumbs}
      </PageHeader>

      <div className="grid grid-cols-1 gap-6">
        {!run ? (
          <Alert variant="info">
            <Info />
            <AlertTitle>Lauf nicht mehr im Board</AlertTitle>
            <AlertDescription>Das Board enthält nur die letzten 20 Läufe. Angezeigt werden die gespeicherten Events.</AlertDescription>
          </Alert>
        ) : null}

        {run && run.escalations.length > 0 ? (
          <section aria-label="Eskalationen" className="grid gap-2" data-testid="escalations">
            {run.escalations.map((e, i) => (
              <Alert key={i} variant={e.open ? 'destructive' : 'default'}>
                <AlertTitle>
                  {e.gate ? labelOf('gate', e.gate) : labelOf('run_state', 'escalated')} · Runde {e.round}
                  {e.open ? ' · offen' : ' · erledigt'}
                </AlertTitle>
                <AlertDescription className="[overflow-wrap:anywhere]">
                  {e.reason} <span className="text-xs opacity-80">({fmtDateTime(e.ts)})</span>
                </AlertDescription>
              </Alert>
            ))}
          </section>
        ) : null}

        {run ? (
          <section aria-label="Runden" className="grid grid-cols-1 gap-4">
            {rounds.length === 0 ? <EmptyState title="Noch keine Station gestartet" /> : rounds.map(([round, stations]) => <RoundCard key={round} round={round} stations={stations} />)}
          </section>
        ) : null}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Zustandsverlauf</CardTitle>
            </CardHeader>
            <CardContent>
              <Timeline events={events} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Event-Log</CardTitle>
              <p className="text-xs text-muted-foreground">Nur Metadaten: Zeiten, Zustände, Zähler und Namen.</p>
            </CardHeader>
            <CardContent>
              <EventLog events={events} />
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
