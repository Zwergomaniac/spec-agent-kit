import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ProjectCard } from '../src/components/ProjectCard'
import type { PortfolioProject } from '../src/types'

const base: PortfolioProject = {
  key: 'proj-a',
  name: 'Projekt A',
  has_board: true,
  board_generated_at: '2026-10-20T08:00:00Z',
  last_ingest_at: '2026-10-20T08:00:00Z',
  last_activity: '2026-10-20T08:00:00Z',
  active_run: null,
  escalation: null,
  attention_count: 2,
  in_progress: 1,
  warnings: [],
}

describe('ProjectCard', () => {
  it('hebt eskalierte Projekte hervor und verlinkt den Lauf', () => {
    render(
      <ProjectCard
        project={{ ...base, escalation: { run_id: '088-20261019-101500', spec: '088-x', reason: 'Rundenlimit erreicht' } }}
      />
    )
    expect(screen.getByTestId('project-card-proj-a')).toHaveAttribute('data-escalated', 'true')
    expect(screen.getByText('Rundenlimit erreicht')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /088-20261019-101500/ })).toHaveAttribute('href', '#/run/proj-a/088-20261019-101500')
  })

  it('zeigt „noch keine Daten“ ohne Board und Warnungen als Liste', () => {
    render(<ProjectCard project={{ ...base, has_board: false, warnings: ['no_push_24h'] }} />)
    expect(screen.getByText(/Noch keine Daten/)).toBeInTheDocument()
    expect(screen.getByLabelText('Warnungen')).toHaveTextContent('Kein Push seit über 24 Std.')
  })

  it('zeigt unbekannte Laufzustände als „unbekannt (wert)“', () => {
    render(
      <ProjectCard
        project={{ ...base, active_run: { run_id: '001-20260101-000000', spec: '001-a', state: 'exploded', round: 1, max_rounds: 2, current_station: null, idle: false, stale: false } }}
      />
    )
    expect(screen.getByText('unbekannt (exploded)')).toBeInTheDocument()
  })
})
