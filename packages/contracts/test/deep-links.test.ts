import { describe, expect, it } from 'vitest'
import { PROJECT_TABS, deepLinks, parseDeepLink } from '../src/index'

const RUN = '012-20261020-140311'

describe('deepLinks (bauen)', () => {
  it('baut die vier URL-Formen aus FR-009', () => {
    expect(deepLinks.portfolio()).toBe('#/portfolio')
    expect(deepLinks.project('ai-forge')).toBe('#/project/ai-forge')
    expect(deepLinks.project('ai-forge', 'attention')).toBe('#/project/ai-forge?tab=attention')
    expect(deepLinks.run('ai-forge', RUN)).toBe(`#/run/ai-forge/${RUN}`)
  })

  it('akzeptiert alle Tabs', () => {
    for (const tab of PROJECT_TABS) expect(deepLinks.project('immo-agent', tab)).toBe(`#/project/immo-agent?tab=${tab}`)
    expect([...PROJECT_TABS]).toEqual(['board', 'runs', 'attention', 'conflicts'])
  })

  it('validiert Projektschlüssel und Lauf-ID', () => {
    for (const bad of ['', 'A', 'a', 'ai_forge', '1abc', 'ab-', 'x'.repeat(41), 'ai forge', 'ai/forge']) {
      expect(() => deepLinks.project(bad), bad).toThrow()
    }
    expect(() => deepLinks.project('ab')).not.toThrow()
    expect(() => deepLinks.project('a'.repeat(40))).not.toThrow()
    expect(() => deepLinks.run('ai-forge', '012-20261020')).toThrow()
    expect(() => deepLinks.run('Bad', RUN)).toThrow()
    expect(() => deepLinks.project('ai-forge', 'unknown' as never)).toThrow()
  })
})

describe('parseDeepLink', () => {
  it('liest die vier Formen, mit und ohne führendes #', () => {
    expect(parseDeepLink('#/portfolio')).toEqual({ view: 'portfolio' })
    expect(parseDeepLink('/portfolio')).toEqual({ view: 'portfolio' })
    expect(parseDeepLink('#/project/ai-forge')).toEqual({ view: 'project', projectKey: 'ai-forge', tab: 'board' })
    expect(parseDeepLink('#/project/ai-forge?tab=conflicts')).toEqual({ view: 'project', projectKey: 'ai-forge', tab: 'conflicts' })
    expect(parseDeepLink(`#/run/ai-forge/${RUN}`)).toEqual({ view: 'run', projectKey: 'ai-forge', runId: RUN })
  })

  it('führt unbekannte Tabs auf board zurück', () => {
    expect(parseDeepLink('#/project/ai-forge?tab=nope')).toEqual({ view: 'project', projectKey: 'ai-forge', tab: 'board' })
    expect(parseDeepLink('#/project/ai-forge?tab=')).toEqual({ view: 'project', projectKey: 'ai-forge', tab: 'board' })
    expect(parseDeepLink('#/project/ai-forge?x=1')).toEqual({ view: 'project', projectKey: 'ai-forge', tab: 'board' })
  })

  it('fällt bei leer, unbekannt oder ungültig auf Portfolio zurück (Startansicht)', () => {
    for (const hash of ['', '#', '#/', '#/nope', '#/project', '#/project/Bad_Key', '#/run/ai-forge', '#/run/ai-forge/xyz', '#/run/BAD/' + RUN, '#/project/a/b']) {
      expect(parseDeepLink(hash), hash).toEqual({ view: 'portfolio' })
    }
  })

  it('ist die Umkehrung des Bauens', () => {
    for (const tab of PROJECT_TABS) {
      expect(parseDeepLink(deepLinks.project('immo-agent', tab))).toEqual({ view: 'project', projectKey: 'immo-agent', tab })
    }
    expect(parseDeepLink(deepLinks.run('immo-agent', RUN))).toEqual({ view: 'run', projectKey: 'immo-agent', runId: RUN })
  })
})
