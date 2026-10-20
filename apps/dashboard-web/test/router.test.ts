import { describe, expect, it } from 'vitest'
import { labelOf } from '../src/labels'
import { links, parseRoute } from '../src/router'

describe('Hash-Router (Deep Links aus @sak/contracts)', () => {
  it('Startansicht ist Portfolio', () => {
    expect(parseRoute('')).toEqual({ view: 'portfolio' })
    expect(parseRoute('#/')).toEqual({ view: 'portfolio' })
    expect(parseRoute('#/portfolio')).toEqual({ view: 'portfolio' })
    expect(parseRoute('#/unbekannt')).toEqual({ view: 'portfolio' })
  })

  it('erkennt Projekt-, Tab- und Lauf-Links', () => {
    expect(parseRoute('#/project/immo-agent')).toEqual({ view: 'project', projectKey: 'immo-agent', tab: 'board' })
    expect(parseRoute('#/project/immo-agent?tab=runs')).toEqual({ view: 'project', projectKey: 'immo-agent', tab: 'runs' })
    expect(parseRoute('#/project/immo-agent?tab=foo')).toMatchObject({ tab: 'board' })
    expect(parseRoute('#/run/immo-agent/088-20261019-101500')).toEqual({
      view: 'run',
      projectKey: 'immo-agent',
      runId: '088-20261019-101500'
    })
  })

  it('erkennt Admin und Login inklusive Rücksprungziel', () => {
    expect(parseRoute('#/admin')).toEqual({ view: 'admin' })
    expect(parseRoute('#/login')).toEqual({ view: 'login', next: null })
    expect(parseRoute(links.login('#/project/a?tab=runs'))).toEqual({ view: 'login', next: '#/project/a?tab=runs' })
    // Kein offenes Weiterleiten auf fremde Ziele.
    expect(parseRoute('#/login?next=https%3A%2F%2Fevil.example')).toEqual({ view: 'login', next: null })
  })

  it('baut Links nur für gültige Schlüssel', () => {
    expect(links.project('immo-agent', 'attention')).toBe('#/project/immo-agent?tab=attention')
    expect(() => links.project('UNGÜLTIG')).toThrow()
  })
})

describe('Labels', () => {
  it('nutzt die deutschen Labels der Contracts', () => {
    expect(labelOf('verdict', 'needs_human')).toBe('Mensch prüft')
    expect(labelOf('stage', 'implementing')).toBe('Umsetzung')
    expect(labelOf('run_state', 'escalated')).toBe('Eskaliert')
  })

  it('zeigt unbekannte Werte als "unbekannt (wert)"', () => {
    expect(labelOf('run_state', 'exploded')).toBe('unbekannt (exploded)')
    expect(labelOf('role', 'qa_bot')).toBe('unbekannt (qa_bot)')
  })

  it('zeigt fehlende Werte als Strich', () => {
    expect(labelOf('verdict', undefined)).toBe('–')
  })
})
