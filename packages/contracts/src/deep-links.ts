// Deep-Link-Helfer für die Dashboard-URLs (Spec 002 FR-009).
//   #/portfolio
//   #/project/:key
//   #/project/:key?tab=board|runs|attention|conflicts
//   #/run/:key/:runId
// Projektschlüssel und Lauf-ID werden beim Bauen und Parsen gegen die Schemas validiert.
import { projectKeySchema, runIdSchema } from './generated/zod'

export const PROJECT_TABS = ['board', 'runs', 'attention', 'conflicts'] as const
export type ProjectTab = (typeof PROJECT_TABS)[number]
export const DEFAULT_TAB: ProjectTab = 'board'

export type DeepLinkRoute =
  | { view: 'portfolio' }
  | { view: 'project'; projectKey: string; tab: ProjectTab }
  | { view: 'run'; projectKey: string; runId: string }

function assertProjectKey(key: string): void {
  if (!projectKeySchema.safeParse(key).success) throw new Error(`Ungültiger Projektschlüssel: ${key}`)
}

function assertRunId(runId: string): void {
  if (!runIdSchema.safeParse(runId).success) throw new Error(`Ungültige Lauf-ID: ${runId}`)
}

export function isProjectTab(value: unknown): value is ProjectTab {
  return typeof value === 'string' && (PROJECT_TABS as readonly string[]).includes(value)
}

export const deepLinks = {
  portfolio: (): string => '#/portfolio',
  /** Ohne Tab: `#/project/:key`; mit Tab: `#/project/:key?tab=<tab>`. */
  project: (projectKey: string, tab?: ProjectTab): string => {
    assertProjectKey(projectKey)
    if (tab === undefined) return `#/project/${projectKey}`
    if (!isProjectTab(tab)) throw new Error(`Unbekannter Tab: ${String(tab)}`)
    return `#/project/${projectKey}?tab=${tab}`
  },
  run: (projectKey: string, runId: string): string => {
    assertProjectKey(projectKey)
    assertRunId(runId)
    return `#/run/${projectKey}/${runId}`
  }
} as const

/**
 * Zerlegt einen Hash (mit oder ohne führendes `#`).
 * Unbekannte Tabs werden zu `board`. Leere, unbekannte oder ungültige Ziele ergeben die
 * Startansicht Portfolio (CLAUDE.md, Regel 3).
 */
export function parseDeepLink(hash: string): DeepLinkRoute {
  const clean = hash.replace(/^#/, '')
  const queryAt = clean.indexOf('?')
  const path = queryAt === -1 ? clean : clean.slice(0, queryAt)
  const params = new URLSearchParams(queryAt === -1 ? '' : clean.slice(queryAt + 1))
  const parts = path.split('/').filter(Boolean)

  if (parts[0] === 'project' && parts.length === 2) {
    const key = parts[1] as string
    if (!projectKeySchema.safeParse(key).success) return { view: 'portfolio' }
    const tab = params.get('tab')
    return { view: 'project', projectKey: key, tab: isProjectTab(tab) ? tab : DEFAULT_TAB }
  }
  if (parts[0] === 'run' && parts.length === 3) {
    const key = parts[1] as string
    const runId = parts[2] as string
    if (projectKeySchema.safeParse(key).success && runIdSchema.safeParse(runId).success) {
      return { view: 'run', projectKey: key, runId }
    }
  }
  return { view: 'portfolio' }
}
