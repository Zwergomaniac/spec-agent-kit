import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/states'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { fmtDateTime, fmtRelative } from '@/format'
import { labelOf, runStateTone } from '@/labels'
import { links, safeLink } from '@/router'
import type { Board } from '@/types'

export function RunsTab({ projectKey, runs }: { projectKey: string; runs: Board['runs'] }) {
  if (runs.length === 0) {
    return <EmptyState title="Noch keine Läufe">Sobald das Projekt einen Lauf startet und einliefert, erscheint er hier.</EmptyState>
  }
  return (
    <div className="rounded-xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Spec</TableHead>
            <TableHead>Lauf</TableHead>
            <TableHead>Zustand</TableHead>
            <TableHead>Art</TableHead>
            <TableHead>Runde</TableHead>
            <TableHead>Herkunft</TableHead>
            <TableHead>Gestartet</TableHead>
            <TableHead>Letztes Ereignis</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((r) => (
            <TableRow key={r.run_id} data-testid={`run-row-${r.run_id}`}>
              <TableCell className="font-medium">{r.spec}</TableCell>
              <TableCell>
                <a href={safeLink(() => links.run(projectKey, r.run_id))} className="font-mono text-xs underline-offset-2 hover:underline">
                  {r.run_id}
                </a>
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant={runStateTone(r.state)}>{labelOf('run_state', r.state)}</Badge>
                  {r.active ? <Badge variant="outline">aktiv</Badge> : null}
                  {r.stale ? <Badge variant="danger">{labelOf('attention_kind', 'stale_run')}</Badge> : r.idle ? <Badge variant="warning">inaktiv</Badge> : null}
                </div>
              </TableCell>
              <TableCell>{labelOf('run_kind', r.kind)}</TableCell>
              <TableCell className="tabular-nums">
                {r.round}/{r.max_rounds}
              </TableCell>
              <TableCell className="text-muted-foreground">
                {[r.origin?.source ? labelOf('run_source', r.origin.source) : null, r.origin?.machine].filter(Boolean).join(' · ') || '–'}
              </TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(r.started_at)}</TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground" title={fmtDateTime(r.last_event_at)}>
                {fmtRelative(r.last_event_at)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
