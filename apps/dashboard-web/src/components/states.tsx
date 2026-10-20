import { AlertCircle, Inbox, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { ApiError } from '@/api'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { fmtTime } from '@/format'
import { cn } from '@/lib/utils'

export function errorMessage(error: Error): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return 'Der Server ist nicht erreichbar.'
    if (error.status === 404) return 'Nicht gefunden.'
    if (error.status >= 500) return 'Der Server meldet einen Fehler.'
  }
  return 'Die Daten konnten nicht geladen werden.'
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertTitle>{errorMessage(error)}</AlertTitle>
      <AlertDescription>
        {onRetry ? (
          <Button variant="outline" size="sm" className="mt-2 text-foreground" onClick={onRetry}>
            <RefreshCw /> Erneut versuchen
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  )
}

export function EmptyState({ title, children, icon, className }: { title: string; children?: ReactNode; icon?: ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col items-center gap-2 rounded-xl border border-dashed px-6 py-10 text-center', className)}>
      <div className="text-muted-foreground [&_svg]:size-6">{icon ?? <Inbox />}</div>
      <p className="font-medium">{title}</p>
      {children ? <div className="max-w-prose text-sm text-muted-foreground">{children}</div> : null}
    </div>
  )
}

export function LoadingView({ rows = 3 }: { rows?: number }) {
  return (
    <div className="grid gap-4" role="status" aria-label="Lädt">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-28 w-full" />
      ))}
    </div>
  )
}

/** Zeigt den Zeitpunkt der letzten Aktualisierung (FR-010) und einen Hinweis bei Verbindungsproblemen. */
export function LastUpdated({ updatedAt, error, onRefresh }: { updatedAt: number | null; error: Error | null; onRefresh: () => void }) {
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground" aria-live="polite">
      {error && updatedAt ? <span className="font-medium text-warning">Verbindung gestört, Stand von vorher.</span> : null}
      <span data-testid="last-updated">{updatedAt ? `Zuletzt aktualisiert: ${fmtTime(updatedAt)}` : 'Lädt …'}</span>
      <Button variant="ghost" size="icon" className="size-7" onClick={onRefresh} aria-label="Jetzt aktualisieren" title="Jetzt aktualisieren">
        <RefreshCw className="size-3.5" />
      </Button>
    </div>
  )
}

export function PageHeader({ title, subtitle, actions, children }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-6 flex scroll-mt-20 flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {children}
        <h1 className="truncate text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? <div className="mt-1 text-sm text-muted-foreground">{subtitle}</div> : null}
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </div>
  )
}
