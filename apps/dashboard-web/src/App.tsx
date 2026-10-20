import { LayoutGrid, LogOut, Monitor, Moon, Settings, Sun } from 'lucide-react'
import { useEffect } from 'react'
import { api } from './api'
import { AuthProvider, useAuth } from './auth'
import { LoadingView } from './components/states'
import { Button } from './components/ui/button'
import { usePolled } from './hooks'
import { links, navigate, useRoute, type Route } from './router'
import { useTheme } from './theme'
import { Admin } from './views/Admin'
import { Login } from './views/Login'
import { Portfolio } from './views/Portfolio'
import { Project } from './views/Project'
import { Run } from './views/Run'

const THEME_LABEL = { system: 'System', light: 'Hell', dark: 'Dunkel' } as const

function titleFor(route: Route): string {
  switch (route.view) {
    case 'portfolio':
      return 'Portfolio'
    case 'project':
      return route.projectKey
    case 'run':
      return `Lauf ${route.runId}`
    case 'admin':
      return 'Admin'
    case 'login':
      return 'Anmelden'
  }
}

function Shell({ children, authenticated }: { children: React.ReactNode; authenticated: boolean }) {
  const route = useRoute()
  const { mode, cycle } = useTheme()
  const { logout } = useAuth()
  const Icon = mode === 'dark' ? Moon : mode === 'light' ? Sun : Monitor
  const navClass = (active: boolean): string =>
    `inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium transition-colors hover:bg-accent ${active ? 'bg-accent text-accent-foreground' : 'text-muted-foreground'}`

  useEffect(() => {
    document.title = `${titleFor(route)} · Spec Agent Dashboard`
  }, [route])

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2">
        Zum Inhalt springen
      </a>
      <header className="sticky top-0 z-40 border-b bg-card/90 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-[1400px] items-center gap-3 px-4 sm:px-6">
          <a href={links.portfolio()} className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground" aria-hidden>
              <LayoutGrid className="size-4" />
            </span>
            <span className="hidden sm:inline">Spec Agent Dashboard</span>
          </a>
          {authenticated ? (
            <nav aria-label="Hauptnavigation" className="ml-2 flex items-center gap-1">
              <a href={links.portfolio()} className={navClass(route.view === 'portfolio')} aria-current={route.view === 'portfolio' ? 'page' : undefined}>
                <LayoutGrid className="size-4" /> Portfolio
              </a>
              <a href={links.admin()} className={navClass(route.view === 'admin')} aria-current={route.view === 'admin' ? 'page' : undefined}>
                <Settings className="size-4" /> Admin
              </a>
            </nav>
          ) : null}
          <div className="ml-auto flex items-center gap-1">
            <Button variant="ghost" size="icon" onClick={cycle} aria-label={`Darstellung: ${THEME_LABEL[mode]} (umschalten)`} title={`Darstellung: ${THEME_LABEL[mode]}`}>
              <Icon />
            </Button>
            {authenticated ? (
              <Button variant="ghost" size="sm" onClick={() => void logout()}>
                <LogOut /> <span className="hidden sm:inline">Abmelden</span>
              </Button>
            ) : null}
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6">
        {children}
      </main>
      {authenticated ? <Footer /> : null}
    </div>
  )
}

function Footer() {
  const { data } = usePolled(api.meta, 'meta', 10 * 60_000)
  return (
    <footer className="border-t py-4 text-center text-xs text-muted-foreground">
      Spec Agent Kit{data ? ` · Dashboard ${data.kit_version} · Vokabular v${data.vocabulary_version}` : ''}
    </footer>
  )
}

function View({ route }: { route: Route }) {
  switch (route.view) {
    case 'portfolio':
      return <Portfolio />
    case 'project':
      return <Project projectKey={route.projectKey} tab={route.tab} />
    case 'run':
      return <Run projectKey={route.projectKey} runId={route.runId} />
    case 'admin':
      return <Admin />
    case 'login':
      return null
  }
}

function Routed() {
  const route = useRoute()
  const { status } = useAuth()

  // Angemeldet auf #/login: weiter zum Rücksprungziel oder zum Portfolio.
  useEffect(() => {
    if (status === 'authenticated' && route.view === 'login') navigate(route.next ?? links.portfolio())
  }, [status, route])

  if (status === 'checking') {
    return (
      <Shell authenticated={false}>
        <LoadingView rows={1} />
      </Shell>
    )
  }
  // Nicht angemeldet: Die Anmeldung erscheint unter der angefragten URL. Nach dem Login
  // rendert dieselbe Route, der Betreiber landet also direkt auf dem Ziel (Deep Link).
  if (status === 'anonymous') {
    return (
      <Shell authenticated={false}>
        <Login />
      </Shell>
    )
  }
  return (
    <Shell authenticated>
      <View route={route} />
    </Shell>
  )
}

export function App() {
  return (
    <AuthProvider>
      <Routed />
    </AuthProvider>
  )
}
