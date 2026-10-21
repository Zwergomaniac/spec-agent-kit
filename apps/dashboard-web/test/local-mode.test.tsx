import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../src/App'
import { detectLocal } from '../src/mode'

const board = {
  schema: 'sak.board/1',
  generated_at: '2026-10-21T09:00:00Z',
  source: 'live',
  kit_version: '0.2.0',
  project: { key: 'proj-a', name: 'Projekt A', base_branch: 'main' },
  metrics: { in_progress: 0, done: 0, blocked: 0, waiting: 0, mean_lead_time_days: null },
  specs: [],
  attention: [],
  runs: [],
  markers: [],
  ticker: [],
  notes: []
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
}

let calls: string[]

function mockFetch(meta: Response | Error): void {
  calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      calls.push(url)
      if (url === '/api/meta') {
        if (meta instanceof Error) throw meta
        return meta.clone()
      }
      if (url === '/api/projects/proj-a')
        return json({ project: { key: 'proj-a', name: 'Projekt A' }, board, ingest: { last_ingest_at: null, board_received_at: null, event_count: 0 } })
      return json({ error: 'not_found' }, 404)
    })
  )
}

beforeEach(() => {
  window.location.hash = ''
})
afterEach(() => vi.unstubAllGlobals())

describe('Lokaler Modus', () => {
  it('wird nur über /api/meta mit mode "local" und project_key erkannt', async () => {
    mockFetch(json({ kit_version: '0.2.0', vocabulary_version: 1, mode: 'local', project_key: 'proj-a' }))
    expect(await detectLocal()).toEqual({ projectKey: 'proj-a' })
    mockFetch(json({ kit_version: '0.2.0', vocabulary_version: 1 }))
    expect(await detectLocal()).toBeNull()
    mockFetch(json({ error: 'unauthorized' }, 401))
    expect(await detectLocal()).toBeNull()
    mockFetch(new Error('offline'))
    expect(await detectLocal()).toBeNull()
  })

  it('startet auf der Projektansicht, ohne Portfolio, Admin und Auth-Aufrufe', async () => {
    mockFetch(json({ kit_version: '0.2.0', vocabulary_version: 1, mode: 'local', project_key: 'proj-a' }))
    const local = await detectLocal()
    render(<App local={local} />)
    await waitFor(() => expect(window.location.hash).toBe('#/project/proj-a'))
    expect(await screen.findByTestId('local-indicator')).toHaveTextContent('Lokal')
    expect(await screen.findByRole('heading', { name: 'Projekt A' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Portfolio/ })).toBeNull()
    expect(screen.queryByRole('link', { name: /Admin/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Abmelden/ })).toBeNull()
    expect(calls.filter((c) => c.includes('/api/auth'))).toEqual([])
    expect(calls.filter((c) => c.includes('/api/portfolio'))).toEqual([])
  })

  it('leitet fremde Routen auf das lokale Projekt um', async () => {
    mockFetch(json({ kit_version: '0.2.0', vocabulary_version: 1, mode: 'local', project_key: 'proj-a' }))
    window.location.hash = '#/admin'
    render(<App local={{ projectKey: 'proj-a' }} />)
    await waitFor(() => expect(window.location.hash).toBe('#/project/proj-a'))
  })

  it('erhält Deep Links auf Tabs', async () => {
    mockFetch(json({}))
    window.location.hash = '#/project/proj-a?tab=runs'
    render(<App local={{ projectKey: 'proj-a' }} />)
    expect(await screen.findByRole('tab', { name: 'Läufe', selected: true })).toBeInTheDocument()
    expect(window.location.hash).toBe('#/project/proj-a?tab=runs')
  })
})
