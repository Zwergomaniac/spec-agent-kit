import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { fmtDays, specNumber } from '@/format'
import type { BoardSpec } from '@/types'
import { EmptyState } from '../states'

const TICK = { fill: 'var(--muted-foreground)', fontSize: 12 }

/** Diagramm 1 (FR-012): Durchlaufzeit je Spec in Tagen. */
export function LeadTimeChart({ specs }: { specs: BoardSpec[] }) {
  const data = specs
    .filter((s) => s.lead_time_days !== undefined)
    .map((s) => ({ name: specNumber(s.number), title: s.title, days: s.lead_time_days as number }))

  return (
    <Card data-testid="chart-lead-time">
      <CardHeader>
        <CardTitle className="text-base">Durchlaufzeit je Spec</CardTitle>
        <CardDescription>Tage von Start bis Abschluss</CardDescription>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <EmptyState title="Noch keine abgeschlossenen Specs" className="py-8" />
        ) : (
          <div role="img" aria-label={`Durchlaufzeit je Spec: ${data.map((d) => `${d.name} ${fmtDays(d.days)}`).join(', ')}`} className="h-56">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis dataKey="name" tick={TICK} tickLine={false} axisLine={false} />
                <YAxis tick={TICK} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip
                  cursor={{ fill: 'var(--muted)' }}
                  contentStyle={{ background: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--popover-foreground)' }}
                  formatter={(v) => [fmtDays(Number(v)), 'Durchlaufzeit']}
                  labelFormatter={(_, payload) => String(payload?.[0]?.payload?.title ?? '')}
                />
                <Bar dataKey="days" fill="var(--info)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
