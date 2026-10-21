import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

const apiTarget = process.env.SAK_API_URL ?? 'http://localhost:3000'

// `vite build --mode board-local` (build:local) baut die UI für `sak board serve` in die Engine:
// relative Asset-Pfade, keine externen Ressourcen, Ausgabe in das eingecheckte Verzeichnis board/web/.
const LOCAL_OUT_DIR = fileURLToPath(new URL('../../packages/engine/src/spec_agent_kit/board/web', import.meta.url))

export default defineConfig(({ mode }) => {
  const local = mode === 'board-local'
  return {
    plugins: [react(), tailwindcss()],
    base: local ? './' : '/',
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) }
    },
    server: {
      port: 5173,
      proxy: {
        '/api': apiTarget,
        '/healthz': apiTarget
      }
    },
    build: {
      outDir: local ? LOCAL_OUT_DIR : 'dist',
      emptyOutDir: true,
      sourcemap: false,
      reportCompressedSize: true,
      chunkSizeWarningLimit: 900
    },
    test: {
      environment: 'jsdom',
      include: ['test/**/*.test.{ts,tsx}'],
      setupFiles: ['./test/setup.ts'],
      css: false
    }
  }
})
