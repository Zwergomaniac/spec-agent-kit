import { PartyPopper } from 'lucide-react'
import { EmptyState } from '@/components/states'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { attentionTone, labelOf } from '@/labels'
import type { Board } from '@/types'

export function AttentionTab({ items }: { items: Board['attention'] }) {
  if (items.length === 0) {
    return (
      <EmptyState title="Nichts offen" icon={<PartyPopper />}>
        Aktuell wartet nichts auf eine Entscheidung des Betreibers.
      </EmptyState>
    )
  }
  return (
    <div className="rounded-xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Art</TableHead>
            <TableHead>Spec</TableHead>
            <TableHead>Grund</TableHead>
            <TableHead>Quelle</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((a, i) => (
            <TableRow key={i} data-testid="attention-row">
              <TableCell>
                <Badge variant={attentionTone(a.kind)}>{labelOf('attention_kind', a.kind)}</Badge>
              </TableCell>
              <TableCell className="min-w-40 font-mono text-xs whitespace-normal [overflow-wrap:anywhere]">{a.spec ?? '–'}</TableCell>
              <TableCell className="min-w-64 whitespace-normal [overflow-wrap:anywhere]">{a.reason}</TableCell>
              <TableCell className="font-mono text-xs whitespace-normal text-muted-foreground [overflow-wrap:anywhere]">{a.source}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
