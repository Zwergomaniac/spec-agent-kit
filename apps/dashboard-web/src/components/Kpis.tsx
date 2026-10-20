import { CheckCircle2, Hourglass, Octagon, Timer, Wrench } from 'lucide-react'
import type { ReactNode } from 'react'
import { Card } from '@/components/ui/card'
import { fmtDays } from '@/format'
import { cn } from '@/lib/utils'
import type { Board } from '@/types'

interface Kpi {
  id: string
  label: string
  value: ReactNode
  icon: ReactNode
  tone?: string
}

export function Kpis({ metrics }: { metrics: Board['metrics'] }) {
  const items: Kpi[] = [
    { id: 'in_progress', label: 'In Arbeit', value: metrics.in_progress, icon: <Wrench />, tone: 'text-info' },
    { id: 'waiting', label: 'Wartet auf Mensch', value: metrics.waiting, icon: <Hourglass />, tone: metrics.waiting > 0 ? 'text-warning' : undefined },
    { id: 'blocked', label: 'Blockiert', value: metrics.blocked, icon: <Octagon />, tone: metrics.blocked > 0 ? 'text-danger' : undefined },
    { id: 'done', label: 'Fertig', value: metrics.done, icon: <CheckCircle2 />, tone: 'text-success' },
    { id: 'lead', label: 'Ø Durchlaufzeit', value: fmtDays(metrics.mean_lead_time_days), icon: <Timer /> }
  ]
  return (
    <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5" aria-label="Kennzahlen">
      {items.map((k) => (
        <Card key={k.id} className="gap-1 py-4" data-testid={`kpi-${k.id}`}>
          <div className="flex items-center justify-between px-4">
            <dt className="text-xs text-muted-foreground">{k.label}</dt>
            <span className={cn('text-muted-foreground [&_svg]:size-4', k.tone)}>{k.icon}</span>
          </div>
          <dd className="px-4 text-2xl font-semibold tabular-nums">{k.value}</dd>
        </Card>
      ))}
    </dl>
  )
}
