// Bündelt API und CLIs mit esbuild nach dist/. @sak/contracts liefert TypeScript-Quellen und wird
// deshalb mitgebündelt; nur das native Modul better-sqlite3 bleibt extern.
import { build } from 'esbuild'
import { rmSync } from 'node:fs'

rmSync(new URL('../dist', import.meta.url), { recursive: true, force: true })

await build({
  entryPoints: ['src/server.ts', 'src/cli/hash-password.ts', 'src/cli/project.ts'],
  outdir: 'dist',
  outbase: 'src',
  bundle: true,
  splitting: true,
  format: 'esm',
  platform: 'node',
  target: 'node22',
  sourcemap: false,
  external: ['better-sqlite3'],
  logLevel: 'info'
})
