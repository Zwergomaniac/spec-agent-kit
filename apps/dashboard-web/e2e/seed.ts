import type { Board, SakEvent } from '@sak/contracts'
import { ADMIN_PASSWORD, BASE_URL, EXTRA_PROJECTS, PILOT_KEY, SECOND_KEY, extraBoard, pilotBoard, pilotEvents, secondBoard } from './fixtures'

async function post(path: string, body: unknown, headers: Record<string, string> = {}): Promise<Response> {
  return fetch(`${BASE_URL}${path}`, { method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: JSON.stringify(body) })
}

async function ingest(token: string, project: string, events: SakEvent[], board: Board): Promise<void> {
  const res = await post(
    '/api/ingest',
    { schema: 'sak.ingest/1', project, sent_at: new Date().toISOString(), events, board },
    { authorization: `Bearer ${token}` }
  )
  if (!res.ok) throw new Error(`Ingest ${project} fehlgeschlagen: ${res.status}`)
  const result = (await res.json()) as { rejected: unknown[]; board_accepted: boolean }
  if (result.rejected.length > 0 || !result.board_accepted) throw new Error(`Ingest ${project}: ${JSON.stringify(result)}`)
}

/** Legt zwei Projekte an und liefert das Pilot-Board samt Events ein (über die echte API). */
export async function seed(): Promise<void> {
  const login = await post('/api/auth/login', { password: ADMIN_PASSWORD })
  if (!login.ok) throw new Error(`Seed-Login fehlgeschlagen: ${login.status}`)
  const cookie = (login.headers.get('set-cookie') ?? '').split(';')[0]!

  const create = async (key: string, name: string): Promise<string> => {
    const res = await post('/api/admin/projects', { key, name }, { cookie })
    if (!res.ok) throw new Error(`Projekt ${key} anlegen: ${res.status}`)
    return ((await res.json()) as { token: string }).token
  }

  const base = pilotBoard()
  const pilotToken = await create(PILOT_KEY, 'ImmoAgent')
  await ingest(pilotToken, PILOT_KEY, pilotEvents(base), base)

  const secondToken = await create(SECOND_KEY, 'Spec Agent Kit')
  await ingest(secondToken, SECOND_KEY, [], secondBoard(base))

  for (const p of EXTRA_PROJECTS) {
    const token = await create(p.key, p.name)
    await ingest(token, p.key, [], extraBoard(base, p.key, p.name, p.specs))
  }
}
