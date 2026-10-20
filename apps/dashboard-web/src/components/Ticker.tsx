import { CheckCheck, GitCommit, Rocket, Newspaper } from 'lucide-react'
import type { ReactNode } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fmtDateTime, fmtRelative } from '@/format'
import { labelOf } from '@/labels'
import type { Board } from '@/types'
import { EmptyState } from './states'

const ICONS: Record<string, ReactNode> = {
  commit: <GitCommit />,
  deploy: <Rocket />,
  verified: <CheckCheck />
}

export function Ticker({ entries }: { entries: Board['ticker'] }) {
  return (
    <Card data-testid="ticker">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Newspaper className="size-4 text-muted-foreground" /> Ticker
        </CardTitle>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <EmptyState title="Noch keine Aktivität" className="py-6" />
        ) : (
          <ol className="max-h-72 space-y-3 overflow-y-auto pr-1">
            {entries.map((t, i) => (
              <li key={`${t.ts}-${i}`} className="flex gap-3 text-sm">
                <span className="mt-0.5 text-muted-foreground [&_svg]:size-4">{ICONS[t.kind] ?? <Newspaper />}</span>
                <div className="min-w-0">
                  <p className="leading-snug">
                    <span className="font-medium">{labelOf('ticker_kind', t.kind)}</span>
                    {t.spec ? <span className="font-mono text-xs text-muted-foreground"> · {t.spec}</span> : null}
                  </p>
                  {t.text ? <p className="truncate text-xs text-muted-foreground" title={t.text}>{t.text}</p> : null}
                  <p className="text-xs text-muted-foreground" title={fmtDateTime(t.ts)}>
                    {fmtRelative(t.ts)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}
