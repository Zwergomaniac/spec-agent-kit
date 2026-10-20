import { Hono } from 'hono'
import { z } from 'zod'
import type { AppDeps } from '../app.js'
import { ProjectError, createProject, listProjects, removeProject, rotateProjectToken } from '../services/projects.js'

const createBody = z.object({ key: z.string().max(64), name: z.string().max(200) }).strict()

function errorStatus(err: ProjectError): 400 | 404 | 409 {
  if (err.code === 'exists') return 409
  if (err.code === 'not_found') return 404
  return 400
}

export function adminRoutes(deps: AppDeps): Hono {
  const app = new Hono()

  app.get('/projects', (c) => c.json({ projects: listProjects(deps.db) }))

  app.post('/projects', async (c) => {
    let raw: unknown
    try {
      raw = await c.req.json()
    } catch {
      return c.json({ error: 'invalid_request' }, 400)
    }
    const body = createBody.safeParse(raw)
    if (!body.success) return c.json({ error: 'invalid_request' }, 400)
    try {
      const { project, token } = createProject(deps.db, body.data.key, body.data.name.trim(), deps.now())
      // Der Klartext-Schlüssel erscheint nur in dieser Antwort.
      return c.json({ project, token }, 201)
    } catch (err) {
      if (err instanceof ProjectError) return c.json({ error: err.code, message: err.message }, errorStatus(err))
      throw err
    }
  })

  app.post('/projects/:key/rotate', (c) => {
    try {
      const { project, token } = rotateProjectToken(deps.db, c.req.param('key'))
      return c.json({ project, token })
    } catch (err) {
      if (err instanceof ProjectError) return c.json({ error: err.code, message: err.message }, errorStatus(err))
      throw err
    }
  })

  app.delete('/projects/:key', (c) => {
    try {
      removeProject(deps.db, c.req.param('key'))
      return c.json({ ok: true })
    } catch (err) {
      if (err instanceof ProjectError) return c.json({ error: err.code, message: err.message }, errorStatus(err))
      throw err
    }
  })

  return app
}
