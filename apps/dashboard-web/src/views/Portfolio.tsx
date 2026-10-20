import { FolderPlus } from 'lucide-react'
import { api } from '@/api'
import { ProjectCard } from '@/components/ProjectCard'
import { EmptyState, ErrorState, LastUpdated, LoadingView, PageHeader } from '@/components/states'
import { Badge } from '@/components/ui/badge'
import { usePolled } from '@/hooks'
import { links } from '@/router'

export function Portfolio() {
  const { data, error, updatedAt, refresh } = usePolled(api.portfolio, 'portfolio')
  const projects = data?.projects ?? []
  // Eskalierte Projekte zuerst, danach nach Schlüssel.
  const sorted = [...projects].sort((a, b) => Number(b.escalation !== null) - Number(a.escalation !== null) || a.key.localeCompare(b.key))
  const escalated = projects.filter((p) => p.escalation).length
  const warned = projects.filter((p) => p.warnings.length > 0).length

  return (
    <>
      <PageHeader
        title="Portfolio"
        subtitle={
          data ? (
            <span className="flex flex-wrap items-center gap-2">
              {projects.length} {projects.length === 1 ? 'Projekt' : 'Projekte'}
              {escalated > 0 ? <Badge variant="danger">{escalated} eskaliert</Badge> : null}
              {warned > 0 ? <Badge variant="warning">{warned} mit Warnung</Badge> : null}
            </span>
          ) : undefined
        }
        actions={<LastUpdated updatedAt={updatedAt} error={error} onRefresh={refresh} />}
      />

      {error && !data ? <ErrorState error={error} onRetry={refresh} /> : null}
      {!data && !error ? <LoadingView /> : null}

      {data && projects.length === 0 ? (
        <EmptyState title="Noch keine Projekte" icon={<FolderPlus />}>
          Lege unter <a className="font-medium text-foreground underline" href={links.admin()}>Admin</a> ein Projekt an und trage den Projekt-Schlüssel im Zielprojekt ein.
        </EmptyState>
      ) : null}

      {data && projects.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {sorted.map((p) => (
            <ProjectCard key={p.key} project={p} />
          ))}
        </div>
      ) : null}
    </>
  )
}
