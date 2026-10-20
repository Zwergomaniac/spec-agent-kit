import { Monitor, Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { links, useRoute } from './router'
import { useTheme } from './theme'

const THEME_LABEL = { system: 'System', light: 'Hell', dark: 'Dunkel' } as const

export function App() {
  const route = useRoute()
  const { mode, cycle } = useTheme()
  const Icon = mode === 'dark' ? Moon : mode === 'light' ? Sun : Monitor

  return (
    <div className="min-h-screen">
      <header className="border-b bg-card">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
          <a href={links.portfolio()} className="font-semibold">
            Spec Agent Dashboard
          </a>
          <Button variant="ghost" size="icon" onClick={cycle} aria-label={`Darstellung: ${THEME_LABEL[mode]}`} title={`Darstellung: ${THEME_LABEL[mode]}`}>
            <Icon />
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <p className="text-sm text-muted-foreground">Ansicht: {route.view}</p>
      </main>
    </div>
  )
}
