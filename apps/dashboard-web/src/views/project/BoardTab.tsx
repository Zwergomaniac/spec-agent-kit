import { vocabulary } from '@sak/contracts'
import { Info } from 'lucide-react'
import type { CSSProperties } from 'react'
import { AttentionList } from '@/components/AttentionList'
import { LeadTimeChart } from '@/components/charts/LeadTimeChart'
import { VerdictChart } from '@/components/charts/VerdictChart'
import { Kpis } from '@/components/Kpis'
import { RunPanel } from '@/components/RunPanel'
import { SpecCard } from '@/components/SpecCard'
import { StageColumn } from '@/components/StageColumn'
import { Ticker } from '@/components/Ticker'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { labelOf } from '@/labels'
import type { Board, BoardRun } from '@/types'

export function BoardTab({ projectKey, board }: { projectKey: string; board: Board }) {
  const activeRun = board.runs.find((r) => r.active)
  const activeSpec = activeRun ? board.specs.find((s) => s.dir === activeRun.spec) : undefined
  // Je Spec der neueste Lauf (Läufe sind neueste zuerst sortiert).
  const runBySpec = new Map<string, BoardRun>()
  for (const r of board.runs) if (!runBySpec.has(r.spec)) runBySpec.set(r.spec, r)

  const descoped = board.specs.filter((s) => s.descoped)
  const staged = board.specs.filter((s) => !s.descoped)
  // Mensch-Spalte plus eine Spalte je Station.
  const columnCount = vocabulary.levels.stage.length + 1

  return (
    <div className="grid grid-cols-1 gap-6">
      <Kpis metrics={board.metrics} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <RunPanel projectKey={projectKey} run={activeRun} spec={activeSpec} />
        <Ticker entries={board.ticker} />
      </div>

      <section aria-label="Board" className="min-w-0">
        {/* Unter 900 px untereinander. 900 bis 1279 px: Spalten mit Mindestbreite, nur das Board scrollt waagerecht.
            Ab 1280 px genau eine Spalte je sichtbarer Spalte, ohne leere Zusatz-Tracks. */}
        <div className="min-w-0 min-[900px]:overflow-x-auto min-[900px]:pb-2 min-[1280px]:overflow-visible min-[1280px]:pb-0" data-testid="board-scroller">
          <div
            className="flex flex-col gap-3 min-[900px]:grid min-[900px]:grid-cols-[repeat(var(--board-cols),minmax(11rem,1fr))] min-[1280px]:grid-cols-[repeat(var(--board-cols),minmax(0,1fr))] min-[1280px]:gap-2 min-[1536px]:gap-3"
            style={{ '--board-cols': columnCount } as CSSProperties}
            data-testid="board-columns"
          >
          <StageColumn id="human" title="Mensch prüft / entscheidet" count={board.attention.length} highlight={board.attention.length > 0}>
            <AttentionList items={board.attention} compact />
          </StageColumn>
          {vocabulary.levels.stage.map((stage) => {
            const specs = staged.filter((s) => s.stage === stage)
            return (
              <StageColumn key={stage} id={stage} title={labelOf('stage', stage)} count={specs.length}>
                <ul className="grid grid-cols-[minmax(0,1fr)] gap-2">
                  {specs.map((s) => (
                    <SpecCard key={s.dir} spec={s} projectKey={projectKey} run={runBySpec.get(s.dir)} />
                  ))}
                </ul>
              </StageColumn>
            )
          })}
          </div>
        </div>
        {descoped.length > 0 ? (
          <details className="mt-3 rounded-xl border bg-card px-4 py-3 text-sm" data-testid="descoped">
            <summary className="cursor-pointer font-medium">Zurückgestellt ({descoped.length})</summary>
            <ul className="mt-2 grid gap-1 text-muted-foreground">
              {descoped.map((s) => (
                <li key={s.dir} className="[overflow-wrap:anywhere]">
                  <span className="font-mono text-xs [overflow-wrap:anywhere]">{s.dir}</span> · {s.title}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <LeadTimeChart specs={board.specs} />
        <VerdictChart runs={board.runs} />
      </div>

      {board.notes.length > 0 ? (
        <Alert variant="info">
          <Info />
          <AlertTitle>Hinweise des Projekts</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-4">
              {board.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}
