import { vocabulary } from '@sak/contracts'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Kpis } from '../src/components/Kpis'
import { SpecCard } from '../src/components/SpecCard'
import { Ticker } from '../src/components/Ticker'
import { HUMAN_COLUMN_DEFINITION, KPI_DEFINITIONS, STAGE_DEFINITIONS } from '../src/definitions'
import type { Board, BoardSpec } from '../src/types'

describe('Definitionen (zentral)', () => {
  it('decken jede Station des Vokabulars und jede Kennzahl ab', () => {
    for (const stage of vocabulary.levels.stage) expect(STAGE_DEFINITIONS[stage], stage).toBeTruthy()
    expect(Object.keys(KPI_DEFINITIONS).sort()).toEqual(['blocked', 'done', 'in_progress', 'lead', 'waiting'])
    expect(HUMAN_COLUMN_DEFINITION).toContain('Freigabe')
  })
})

describe('Kennzahl-Tooltips', () => {
  const metrics: Board['metrics'] = { in_progress: 1, done: 2, blocked: 0, waiting: 3, mean_lead_time_days: 2 }

  it('erscheinen per Fokus (Tastatur) und verschwinden mit Escape', async () => {
    const user = userEvent.setup()
    render(<Kpis metrics={metrics} />)
    await user.tab()
    expect(screen.getByRole('tooltip')).toHaveTextContent(/In Arbeit = /)
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('erscheinen per Mauszeiger', async () => {
    const user = userEvent.setup()
    render(<Kpis metrics={metrics} />)
    await user.hover(screen.getByTestId('kpi-tip-done'))
    expect(screen.getByRole('tooltip')).toHaveTextContent(KPI_DEFINITIONS.done)
  })
})

describe('Ticker-Details', () => {
  const entries: Board['ticker'] = [
    { ts: '2026-10-21T09:30:15Z', kind: 'commit', spec: '088-foo', text: 'feat(088): Betreff', commit: 'abc1234' },
    { ts: '2026-10-21T08:00:00Z', kind: 'deploy' }
  ]

  it('zeigt Hash, Zeit mit Zone, Spec und Betreff bei Fokus', async () => {
    const user = userEvent.setup()
    render(<Ticker entries={entries} />)
    await user.tab()
    const tip = screen.getByRole('tooltip')
    expect(tip).toHaveTextContent('abc1234')
    expect(tip).toHaveTextContent('088-foo')
    expect(tip).toHaveTextContent('feat(088): Betreff')
    expect(tip).toHaveTextContent(/\d{2}:\d{2}:\d{2} \S+/)
  })

  it('markiert fehlenden Betreff und fehlenden Hash', async () => {
    const user = userEvent.setup()
    render(<Ticker entries={entries} />)
    await user.hover(screen.getAllByTestId('ticker-item')[1]!)
    expect(screen.getByRole('tooltip')).toHaveTextContent('nicht geteilt')
    expect(screen.getByRole('tooltip')).toHaveTextContent('nicht verfügbar')
  })
})

describe('tasks.partial', () => {
  const spec = {
    number: 18,
    dir: '018-x',
    title: 'X',
    descoped: false,
    blocked: false,
    waiting: null,
    tasks: { done: 3, open: 2, partial: 1 },
    stage: 'implementing'
  } as BoardSpec

  it('zählt teilweise erledigte Tasks zur Gesamtzahl und zeigt sie an', () => {
    render(
      <ul>
        <SpecCard spec={spec} projectKey="p" />
      </ul>
    )
    expect(screen.getByText(/3 von 6 Tasks/)).toBeInTheDocument()
    expect(screen.getByTestId('tasks-partial')).toHaveTextContent('1 teilweise')
  })

  it('zeigt nichts ohne partial', () => {
    render(
      <ul>
        <SpecCard spec={{ ...spec, tasks: { done: 3, open: 2 } }} projectKey="p" />
      </ul>
    )
    expect(screen.queryByTestId('tasks-partial')).toBeNull()
  })
})
