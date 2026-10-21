import { isProjectTab, type ProjectTab } from '@sak/contracts'
import { ChevronRight, FileQuestion } from 'lucide-react'
import { useEffect } from 'react'
import { api, ApiError } from '@/api'
import { EmptyState, ErrorState, LastUpdated, LoadingView, PageHeader } from '@/components/states'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { fmtDateTime } from '@/format'
import { usePolled } from '@/hooks'
import { labelOf } from '@/labels'
import { useMode } from '@/mode'
import { links, navigate } from '@/router'
import { AttentionTab } from './project/AttentionTab'
import { BoardTab } from './project/BoardTab'
import { ConflictsTab } from './project/ConflictsTab'
import { RunsTab } from './project/RunsTab'

export function Project({ projectKey, tab }: { projectKey: string; tab: ProjectTab }) {
  const { data, error, updatedAt, refresh } = usePolled(() => api.project(projectKey), `project:${projectKey}`)
  const { local, setProjectName } = useMode()
  const name = data?.project.name
  useEffect(() => {
    if (local && name) setProjectName(name)
  }, [local, name, setProjectName])

  const crumbs = (
    <nav aria-label="Brotkrumen" className="mb-2 flex items-center gap-1 text-xs text-muted-foreground">
      {local ? null : (
        <>
          <a href={links.portfolio()} className="hover:underline">
            Portfolio
          </a>
          <ChevronRight className="size-3" />
        </>
      )}
      <span className="font-mono">{projectKey}</span>
    </nav>
  )

  if (error instanceof ApiError && error.status === 404) {
    return (
      <>
        <PageHeader title="Projekt nicht gefunden">{crumbs}</PageHeader>
        <EmptyState title={`Es gibt kein Projekt „${projectKey}“`} icon={<FileQuestion />}>
          {local ? null : (
            <a href={links.portfolio()} className="underline">
              Zurück zum Portfolio
            </a>
          )}
        </EmptyState>
      </>
    )
  }
  if (!data) {
    return (
      <>
        <PageHeader title={projectKey}>{crumbs}</PageHeader>
        {error ? <ErrorState error={error} onRetry={refresh} /> : <LoadingView />}
      </>
    )
  }

  const board = data.board
  const attentionCount = board?.attention.length ?? 0

  return (
    <>
      <PageHeader
        title={data.project.name}
        subtitle={
          board ? (
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-mono">{data.project.key}</span>
              <span>Branch {board.project.base_branch}</span>
              <Badge variant={board.source === 'live' ? 'success' : 'secondary'}>{labelOf('board_source', board.source)}</Badge>
              <span title={board.generated_at}>Stand {fmtDateTime(board.generated_at)}</span>
              <span>Kit {board.kit_version}</span>
            </span>
          ) : (
            <span className="font-mono">{data.project.key}</span>
          )
        }
        actions={<LastUpdated updatedAt={updatedAt} error={error} onRefresh={refresh} />}
      >
        {crumbs}
      </PageHeader>

      {!board ? (
        <EmptyState title="Noch keine Daten">
          Dieses Projekt hat noch kein Board eingeliefert. Sobald der erste Push ankommt, erscheint es hier.
        </EmptyState>
      ) : (
        <Tabs value={tab} data-testid="project-tabs" onValueChange={(v) => isProjectTab(v) && navigate(links.project(projectKey, v))}>
          <TabsList aria-label="Projektansicht">
            <TabsTrigger value="board">Board</TabsTrigger>
            <TabsTrigger value="runs">Läufe</TabsTrigger>
            <TabsTrigger value="attention">
              Aufmerksamkeit
              {attentionCount > 0 ? <Badge variant="warning">{attentionCount}</Badge> : null}
            </TabsTrigger>
            <TabsTrigger value="conflicts">Konflikte</TabsTrigger>
          </TabsList>
          <TabsContent value="board">
            <BoardTab projectKey={projectKey} board={board} />
          </TabsContent>
          <TabsContent value="runs">
            <RunsTab projectKey={projectKey} runs={board.runs} />
          </TabsContent>
          <TabsContent value="attention">
            <AttentionTab items={board.attention} />
          </TabsContent>
          <TabsContent value="conflicts">
            <ConflictsTab />
          </TabsContent>
        </Tabs>
      )}
    </>
  )
}
