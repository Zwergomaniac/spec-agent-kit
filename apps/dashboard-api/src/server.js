import { Hono } from 'hono'

const app = new Hono()
const sampleProjects = [
  { project_key: 'immo-agent', name: 'ImmoAgent', default_branch: 'main', active_runs: 3, waiting_on_operator: 2, conflicts: 1, last_activity: '2026-10-20T10:20:00+02:00' },
  { project_key: 'spec-agent-kit', name: 'Spec Agent Kit', default_branch: 'main', active_runs: 1, waiting_on_operator: 0, conflicts: 0, last_activity: '2026-10-20T10:18:00+02:00' }
]
const sampleRuns = [
  { run_id: '093-abc', project_key: 'immo-agent', spec_id: '093', stage: 'review', status: 'needs_changes', branch: '093-agent-pipeline', active_agents: ['builder','code-reviewer','ui-reviewer'], verdict: 'Änderung' },
  { run_id: '092-def', project_key: 'immo-agent', spec_id: '092', stage: 'operator_wait', status: 'operator_wait', branch: '092-dev-dashboard', active_agents: ['integrator'], verdict: 'Mensch prüft' }
]
const events = []

app.get('/health', (c) => c.json({ ok: true, service: 'dashboard-api', defaultView: 'portfolio' }))
app.get('/api/meta', (c) => c.json({ defaultView: 'portfolio', routes: ['#/portfolio', '#/project/:projectKey', '#/project/:projectKey?tab=board', '#/project/:projectKey?tab=conflicts', '#/run/:projectKey/:runId'] }))
app.get('/api/projects', (c) => c.json({ items: sampleProjects }))
app.get('/api/runs', (c) => c.json({ items: sampleRuns }))
app.post('/api/events', async (c) => { const payload = await c.req.json(); events.push(payload); return c.json({ accepted: true, count: events.length }) })

export default app
