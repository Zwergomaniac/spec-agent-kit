export type RouteState =
  | { view: 'portfolio' }
  | { view: 'project'; projectKey: string; tab: string }
  | { view: 'run'; projectKey: string; runId: string }

export function parseHash(hash: string): RouteState {
  const clean = hash.replace(/^#/, '') || '/portfolio'
  const [path, queryString] = clean.split('?')
  const parts = path.split('/').filter(Boolean)
  const params = new URLSearchParams(queryString || '')
  if (parts[0] === 'project' && parts[1]) return { view: 'project', projectKey: parts[1], tab: params.get('tab') || 'board' }
  if (parts[0] === 'run' && parts[1] && parts[2]) return { view: 'run', projectKey: parts[1], runId: parts[2] }
  return { view: 'portfolio' }
}
