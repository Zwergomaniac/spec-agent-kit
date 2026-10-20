import { readFile, stat } from 'node:fs/promises'
import { extname, join, resolve, sep } from 'node:path'
import type { Context } from 'hono'

const TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.txt': 'text/plain; charset=utf-8',
  '.map': 'application/json'
}

/**
 * Liefert die gebaute UI aus. Pfade ohne Dateiendung fallen auf index.html zurück (SPA-Fallback);
 * fehlende Dateien mit Endung ergeben 404. Zugriffe außerhalb von `root` werden abgewiesen.
 */
export function createStaticHandler(webDist: string): (c: Context) => Promise<Response> {
  const root = resolve(webDist)

  return async (c) => {
    const method = c.req.method
    if (method !== 'GET' && method !== 'HEAD') return c.json({ error: 'not_found' }, 404)

    let pathname: string
    try {
      pathname = decodeURIComponent(new URL(c.req.url).pathname)
    } catch {
      return c.json({ error: 'not_found' }, 404)
    }
    if (pathname.startsWith('/api/') || pathname === '/api') return c.json({ error: 'not_found' }, 404)

    const candidate = resolve(join(root, pathname === '/' ? 'index.html' : pathname))
    const inside = candidate === root || candidate.startsWith(root + sep)
    const ext = extname(candidate)

    if (inside && ext) {
      const file = await tryRead(candidate)
      if (file) return respond(c, file, ext, pathname.startsWith('/assets/'))
      return c.json({ error: 'not_found' }, 404)
    }
    if (ext) return c.json({ error: 'not_found' }, 404)

    const index = await tryRead(join(root, 'index.html'))
    if (!index) return c.json({ error: 'ui_not_built' }, 404)
    return respond(c, index, '.html', false)
  }
}

async function tryRead(path: string): Promise<Buffer | null> {
  try {
    const s = await stat(path)
    if (!s.isFile()) return null
    return await readFile(path)
  } catch {
    return null
  }
}

function respond(c: Context, body: Buffer, ext: string, immutable: boolean): Response {
  const headers: Record<string, string> = {
    'Content-Type': TYPES[ext] ?? 'application/octet-stream',
    // Gehashte Vite-Assets sind unveränderlich; index.html muss immer neu validiert werden.
    'Cache-Control': immutable ? 'public, max-age=31536000, immutable' : 'no-cache'
  }
  return new Response(c.req.method === 'HEAD' ? null : new Uint8Array(body), { status: 200, headers })
}
