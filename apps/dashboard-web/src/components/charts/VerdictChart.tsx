import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { labelOf } from '@/labels'
import type { BoardRun } from '@/types'
import { EmptyState } from '../states'

const TICK = { fill: 'var(--muted-foreground)', fontSize: 12 }
const SERIES = [
  { key: 'approve', color: 'var(--success)' },
  { key: 'changes_requested', color: 'var(--warning)' },
  { key: 'needs_human', color: 'var(--danger)' }
] as const

export function verdictsByRound(runs: BoardRun[]): Array<Record<string, number | string>> {
  const rounds = new Map<number, Record<string, number>>()
  for (const run of runs) {
    for (const s of run.stations) {
      if (!s.verdict) continue
      const row = rounds.get(s.round) ?? { approve: 0, changes_requested: 0, needs_human: 0 }
      row[s.verdict] = (row[s.verdict] ?? 0) + 1
      rounds.set(s.round, row)
    }
  }
  return [...rounds.entries()].sort((a, b) => a[0] - b[0]).map(([round, row]) => ({ name: `Runde ${round}`, ...row }))
}

/** Diagramm 2 (FR-012): Urteile je Runde, über alle Läufe im Board. */
export function VerdictChart({ runs }: { runs: BoardRun[] }) {
  const data = verdictsByRound(runs)

  return (
    <Card data-testid="chart-verdicts">
      <CardHeader>
        <CardTitle className="text-base">Urteile je Runde</CardTitle>
        <CardDescription>Anzahl Urteile aller Prüf-Stationen</CardDescription>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <EmptyState title="Noch keine Urteile" className="py-8" />
        ) : (
          <div
            role="img"
            aria-label={`Urteile je Runde: ${data.map((d) => `${d.name}: ${SERIES.map((s) => `${labelOf('verdict', s.key)} ${d[s.key]}`).join(', ')}`).join('; ')}`}
            className="h-56"
          >
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis dataKey="name" tick={TICK} tickLine={false} axisLine={false} />
                <YAxis tick={TICK} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip
                  cursor={{ fill: 'var(--muted)' }}
                  contentStyle={{ background: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--popover-foreground)' }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                {SERIES.map((s) => (
                  <Bar key={s.key} dataKey={s.key} name={labelOf('verdict', s.key)} stackId="v" fill={s.color} isAnimationActive={false} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
