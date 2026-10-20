export type EventEnvelope<T = Record<string, unknown>> = {
  version: '1'
  event_id: string
  event_type: string
  timestamp: string
  project: string
  data: T
}

export const DASHBOARD_DEEP_LINKS = {
  portfolio: '#/portfolio',
  project: (projectKey: string) => `#/project/${projectKey}`,
  projectTab: (projectKey: string, tab: string) => `#/project/${projectKey}?tab=${tab}`,
  run: (projectKey: string, runId: string) => `#/run/${projectKey}/${runId}`
} as const
