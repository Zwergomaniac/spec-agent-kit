import { LayoutGrid, LogOut, Monitor, Moon, Settings, Sun } from 'lucide-react'
import { useEffect } from 'react'
import { api } from './api'
import { AuthProvider, useAuth } from './auth'
import { LoadingView } from './components/states'
import { Button } from './components/ui/button'
import { Badge } from './components/ui/badge'
import { usePolled } from './hooks'
import { ModeProvider, useMode, type LocalInfo } from './mode'
import { links, navigate, replaceRoute, useRoute, type Route } from './router'
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

function Shell({ children, authenticated, onLogout }: { children: React.ReactNode; authenticated: boolean; onLogout?: () => void }) {
  const route = useRoute()
  const { mode, cycle } = useTheme()
  const { local, projectName } = useMode()
  const Icon = mode === 'dark' ? Moon : mode === 'light' ? Sun : Monitor
  const navClass = (active: boolean): string =>
    `inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-sm font-medium transition-colors hover:bg-accent ${active ? 'bg-accent text-accent-foreground' : 'text-muted-foreground'}`

  useEffect(() => {
    document.title = local ? `${titleFor(route)} · Lokal · Spec Agent Dashboard` : `${titleFor(route)} · Spec Agent Dashboard`
  }, [route, local])

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2">
        Zum Inhalt springen
      </a>
      <header className="sticky top-0 z-40 border-b bg-card/90 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-[2400px] items-center gap-3 px-4 sm:px-6 lg:px-10">
          <a href={local ? links.project(local.projectKey) : links.portfolio()} className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground" aria-hidden>
              <LayoutGrid className="size-4" />
            </span>
            <span className="hidden sm:inline">Spec Agent Dashboard</span>
          </a>
          {local ? (
            <div className="ml-2 flex min-w-0 items-center gap-2 text-sm" data-testid="local-indicator">
              <Badge variant="info">Lokal</Badge>
              <span className="truncate font-medium">{projectName ?? local.projectKey}</span>
            </div>
          ) : null}
          {authenticated && !local ? (
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
            {authenticated && !local ? (
              <Button variant="ghost" size="sm" onClick={() => void onLogout?.()}>
                <LogOut /> <span className="hidden sm:inline">Abmelden</span>
              </Button>
            ) : null}
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-[2400px] flex-1 px-4 py-6 sm:px-6 lg:px-10">
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
  const { status, logout } = useAuth()

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
    <Shell authenticated onLogout={logout}>
      <View route={route} />
    </Shell>
  )
}

/** Lokaler Modus: nur die Ansichten des einen Projekts. Alles andere führt zur Projektansicht; es gibt keine Auth-Aufrufe. */
function LocalRouted({ local }: { local: LocalInfo }) {
  const route = useRoute()
  const allowed = (route.view === 'project' || route.view === 'run') && route.projectKey === local.projectKey
  useEffect(() => {
    if (!allowed) replaceRoute(links.project(local.projectKey))
  }, [allowed, local.projectKey])
  return <Shell authenticated>{allowed ? <View route={route} /> : null}</Shell>
}

export function App({ local = null }: { local?: LocalInfo | null }) {
  return (
    <ModeProvider local={local}>
      {local ? (
        <LocalRouted local={local} />
      ) : (
        <AuthProvider>
          <Routed />
        </AuthProvider>
      )}
    </ModeProvider>
  )
}
