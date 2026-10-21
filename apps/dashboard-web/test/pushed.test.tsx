import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RunPanel } from '../src/components/RunPanel'
import { describeEvent, eventTypeLabel } from '../src/eventText'
import type { BoardRun, SakEvent } from '../src/types'

const run: BoardRun = {
  run_id: '088-20261019-101500',
  spec: '088-kartenansicht',
  kind: 'pipeline',
  state: 'merged',
  round: 1,
  max_rounds: 2,
  active: false,
  started_at: '2026-10-19T10:00:00Z',
  updated_at: '2026-10-19T10:20:00Z',
  last_event_at: '2026-10-19T10:20:00Z',
  idle: false,
  stale: false,
  stations: [],
  escalations: []
}

describe('Push-Anzeige (Spec 012)', () => {
  it('zeigt „gepusht“ im Agenten-Panel nur bei gepushtem Lauf', () => {
    const { rerender } = render(<RunPanel projectKey="demo" run={run} spec={undefined} />)
    expect(screen.queryByTestId('pushed-badge')).toBeNull()
    rerender(<RunPanel projectKey="demo" run={{ ...run, pushed: true }} spec={undefined} />)
    expect(screen.getByTestId('pushed-badge')).toHaveTextContent('gepusht')
  })

  it('beschriftet das Event im Event-Log mit Remote, Branch und Commit', () => {
    const event = {
      schema: 'sak.event/1',
      event_id: '01K8M3Q7R50000000000000042',
      type: 'run.pushed',
      ts: '2026-10-19T10:16:00+02:00',
      project: 'demo',
      run_id: run.run_id,
      data: { remote: 'origin', branch: 'main', commit: '0f1e2d3c4b5a69788796a5b4c3d2e1f001122334' }
    } as SakEvent
    expect(eventTypeLabel('run.pushed')).toBe('Gepusht')
    expect(describeEvent(event)).toBe('origin/main · Commit 0f1e2d3c')
  })
})
