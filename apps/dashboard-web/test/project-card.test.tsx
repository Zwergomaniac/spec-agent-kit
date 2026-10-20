import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
  stage_counts: { specified: 1, clarified: 0, planned: 0, tasked: 0, implementing: 2, implemented: 0, deployed: 0, verified: 3 },
  done: 3,
  attention_preview: [],
  attention_total: 0,
  last_marker: null,
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

  describe('ganze Karte anklickbar (Stretched Link)', () => {
    it('hat genau einen Hauptlink auf das Board mit Pseudo-Element über die ganze Karte', () => {
      render(<ProjectCard project={base} />)
      const card = screen.getByTestId('project-card-proj-a')
      const main = within(card).getByRole('link', { name: 'Projekt A' })
      expect(main).toHaveAttribute('href', '#/project/proj-a')
      expect(main.className).toContain('after:absolute')
      expect(main.className).toContain('after:inset-0')
      expect(card.className).toContain('relative')
      expect(card.className).toContain('cursor-pointer')
      // Kein div mit onClick: Die Navigation läuft über die semantische <a>.
      expect(card.getAttribute('onclick')).toBeNull()
    })

    it('hält innere Links über dem Stretched Link', () => {
      render(
        <ProjectCard
          project={{
            ...base,
            escalation: { run_id: '088-20261019-101500', spec: '088-x', reason: 'Rundenlimit' },
            active_run: { run_id: '088-20261019-101500', spec: '088-x', state: 'escalated', round: 2, max_rounds: 2, current_station: null, idle: false, stale: false }
          }}
        />
      )
      for (const link of screen.getAllByRole('link', { name: /Lauf/ })) expect(link.className).toContain('z-10')
    })

    it('ist per Tastatur fokussierbar: Tab landet auf dem Hauptlink', async () => {
      render(<ProjectCard project={base} />)
      await userEvent.tab()
      expect(screen.getByRole('link', { name: 'Projekt A' })).toHaveFocus()
    })

    it('zeigt den Hinweis „Board öffnen“', () => {
      render(<ProjectCard project={base} />)
      expect(screen.getByTestId('open-hint')).toHaveTextContent('Board öffnen')
    })
  })

  describe('Inhalt', () => {
    it('zeigt Stationsbalken mit Tooltip je Segment und fertige Specs', () => {
      render(<ProjectCard project={base} />)
      const bar = screen.getByTestId('stage-bar')
      const segments = bar.querySelectorAll('a[data-stage]')
      expect(Array.from(segments).map((a) => a.getAttribute('data-stage'))).toEqual(['specified', 'implementing', 'verified'])
      expect(segments[1]).toHaveAttribute('title', 'Umsetzung: 2 Specs')
      expect(segments[0]).toHaveAttribute('title', 'Spec: 1 Spec')
      expect(segments[0]).toHaveAttribute('tabindex', '-1')
      expect(screen.getByText('Fertig').closest('div')).toHaveTextContent('3')
    })

    it('zeigt höchstens 3 Aufmerksamkeitseinträge und „+N weitere“', () => {
      render(
        <ProjectCard
          project={{
            ...base,
            attention_count: 5,
            attention_total: 5,
            attention_preview: [
              { kind: 'escalation', spec: '088-a' },
              { kind: 'approval', spec: '090-b' },
              { kind: 'blocker', spec: '092-c' }
            ]
          }}
        />
      )
      const list = screen.getByTestId('attention-preview')
      expect(within(list).getAllByRole('listitem')).toHaveLength(4)
      expect(list).toHaveTextContent('088-a')
      expect(list).toHaveTextContent('+2 weitere')
    })

    it('zeigt den letzten Deploy-Marker', () => {
      render(<ProjectCard now={Date.parse('2026-10-20T10:00:00Z')} project={{ ...base, last_marker: { kind: 'deploy', ts: '2026-10-20T08:00:00Z', specs: [66] } }} />)
      expect(screen.getByTestId('last-marker')).toHaveTextContent('Deploy vor 2 Std. · #066')
    })
  })
})
