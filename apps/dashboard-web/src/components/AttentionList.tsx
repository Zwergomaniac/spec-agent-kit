import { Badge } from '@/components/ui/badge'
import { attentionTone, labelOf } from '@/labels'
import type { BoardAttention } from '@/types'

/** Einträge „Mensch prüft / entscheidet“: Art, Spec, Grund und Quelle. */
export function AttentionList({ items, compact = false }: { items: BoardAttention[]; compact?: boolean }) {
  return (
    <ul className="grid gap-2">
      {items.map((a, i) => (
        <li key={`${a.kind}-${a.spec ?? ''}-${a.source}-${i}`} className="rounded-lg border bg-card p-3 text-sm shadow-xs" data-testid="attention-item">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={attentionTone(a.kind)}>{labelOf('attention_kind', a.kind)}</Badge>
            {a.spec ? <span className="font-mono text-xs text-muted-foreground">{a.spec}</span> : null}
          </div>
          <p className="mt-1.5 leading-snug">{a.reason}</p>
          {!compact ? (
            <p className="mt-1 truncate font-mono text-xs text-muted-foreground" title={a.source}>
              Quelle: {a.source}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  )
}
