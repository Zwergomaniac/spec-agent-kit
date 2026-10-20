import { vocabulary } from '@sak/contracts'
import { AlertTriangle, ArrowRight, BellRing, CheckCircle2, Clock, Cpu, Layers, Rocket, WifiOff } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { fmtDateTime, fmtRelative, specNumber } from '@/format'
import { attentionTone, labelOf, runStateTone } from '@/labels'
import { links, safeLink } from '@/router'
import type { PortfolioProject, PortfolioWarning } from '@/types'
import { cn } from '@/lib/utils'

const WARNING_TEXT: Record<PortfolioWarning, string> = {
  stale: labelOf('attention_kind', 'stale_run'),
  idle: 'Lauf inaktiv',
  no_push_24h: 'Kein Push seit über 24 Std.'
}

/** Farbverlauf der Stationen: von neutral (früh) über blau (in Arbeit) nach grün (live). */
const STAGE_COLOR: Record<string, string> = {
  specified: 'bg-muted-foreground/30',
  clarified: 'bg-muted-foreground/50',
  planned: 'bg-info/35',
  tasked: 'bg-info/55',
  implementing: 'bg-info',
  implemented: 'bg-success/55',
  deployed: 'bg-success/80',
  verified: 'bg-success'
}

/** Bar über die Stationen. Die Segmente führen (ohne eigenen Tab-Stopp) zum Board, damit ein Klick die Karte öffnet. */
function StageBar({ counts, href }: { counts: Record<string, number>; href: string }) {
  const segments = vocabulary.levels.stage.map((stage) => ({ stage, count: counts[stage] ?? 0 })).filter((s) => s.count > 0)
  const total = segments.reduce((sum, s) => sum + s.count, 0)
  if (total === 0) return null
  const summary = segments.map((s) => `${labelOf('stage', s.stage)}: ${s.count}`).join(', ')
  return (
    <div className="grid gap-1.5" data-testid="stage-bar">
      <div className="flex h-2 w-full gap-px overflow-hidden rounded-full bg-muted" aria-hidden>
        {segments.map((s) => (
          <a
            key={s.stage}
            href={href}
            tabIndex={-1}
            title={`${labelOf('stage', s.stage)}: ${s.count} ${s.count === 1 ? 'Spec' : 'Specs'}`}
            data-stage={s.stage}
            style={{ flexGrow: s.count }}
            className={cn('relative z-10 h-full min-w-1.5 basis-0 transition-opacity hover:opacity-80', STAGE_COLOR[s.stage])}
          />
        ))}
      </div>
      <p className="sr-only">Verteilung der Specs: {summary}</p>
    </div>
  )
}

function Stat({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: number; tone?: string }) {
  return (
    <div>
      <dt className="flex items-center gap-1 text-xs text-muted-foreground [&>svg]:size-3">
        {icon} <span>{label}</span>
      </dt>
      <dd className={cn('text-xl font-semibold tabular-nums', tone)}>{value}</dd>
    </div>
  )
}

export function ProjectCard({ project, now }: { project: PortfolioProject; now?: number }) {
  const escalated = project.escalation !== null
  const run = project.active_run
  const projectHref = safeLink(() => links.project(project.key))
  const hidden = Math.max(0, project.attention_total - project.attention_preview.length)
  const marker = project.last_marker

  return (
    <Card
      className={cn(
        // Stretched Link: der Titel-Link spannt per ::after die ganze Karte auf (position: relative hier).
        'group relative min-w-0 cursor-pointer gap-4 transition-[border-color,box-shadow,transform] duration-150',
        'hover:border-foreground/25 hover:shadow-lg hover:shadow-foreground/5 motion-safe:hover:-translate-y-0.5',
        'has-[a[data-card-link]:focus-visible]:border-ring has-[a[data-card-link]:focus-visible]:ring-2 has-[a[data-card-link]:focus-visible]:ring-ring/50',
        escalated && 'border-danger/50 bg-danger-soft/30 hover:border-danger/70'
      )}
      data-testid={`project-card-${project.key}`}
      data-escalated={escalated}
    >
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <CardTitle className="truncate text-lg">
            <a
              href={projectHref}
              data-card-link
              className="rounded-sm outline-none after:absolute after:inset-0 after:z-0 after:rounded-xl after:content-['']"
            >
              {project.name}
            </a>
          </CardTitle>
          <p className="font-mono text-xs text-muted-foreground">{project.key}</p>
        </div>
        {escalated ? (
          <Badge variant="danger">
            <AlertTriangle /> {labelOf('run_state', 'escalated')}
          </Badge>
        ) : null}
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-4">
        {escalated && project.escalation ? (
          <div className="rounded-lg border border-danger/40 bg-card/70 p-3 text-sm">
            <p className="font-medium text-danger [overflow-wrap:anywhere]">{project.escalation.reason ?? 'Eskalation ohne Angabe eines Grundes'}</p>
            <a
              href={safeLink(() => links.run(project.key, project.escalation!.run_id))}
              className="relative z-10 mt-1 inline-flex items-center gap-1 text-xs font-medium underline-offset-2 hover:underline"
            >
              Lauf {project.escalation.run_id} öffnen <ArrowRight className="size-3" />
            </a>
          </div>
        ) : null}

        {!project.has_board ? (
          <p className="text-sm text-muted-foreground">Noch keine Daten. Das Projekt hat bisher kein Board eingeliefert.</p>
        ) : run ? (
          <div className="grid gap-1.5 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={runStateTone(run.state)}>{labelOf('run_state', run.state)}</Badge>
              <span className="min-w-0 font-medium [overflow-wrap:anywhere]">{run.spec}</span>
            </div>
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span>
                Runde {run.round} von {run.max_rounds}
              </span>
              {run.current_station ? (
                <span className="inline-flex items-center gap-1">
                  <Cpu className="size-3" />
                  {labelOf('role', run.current_station.role)}
                  <span className="font-mono">{run.current_station.agent}</span>
                </span>
              ) : null}
              <a
                href={safeLink(() => links.run(project.key, run.run_id))}
                className="relative z-10 font-medium text-foreground underline-offset-2 hover:underline"
              >
                Lauf ansehen
              </a>
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Kein aktiver Lauf.</p>
        )}

        {project.has_board ? (
          <>
            <StageBar counts={project.stage_counts} href={projectHref} />

            <dl className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
              <Stat icon={<BellRing />} label="Aufmerksamkeit" value={project.attention_count} tone={project.attention_count > 0 ? 'text-warning' : undefined} />
              <Stat icon={<Layers />} label="In Arbeit" value={project.in_progress} />
              <Stat icon={<CheckCircle2 />} label="Fertig" value={project.done} />
            </dl>

            {project.attention_preview.length > 0 ? (
              <ul className="grid gap-1.5 text-sm" aria-label="Aufmerksamkeit" data-testid="attention-preview">
                {project.attention_preview.map((a, i) => (
                  <li key={`${a.kind}-${a.spec}-${i}`} className="flex min-w-0 items-center gap-2">
                    <Badge variant={attentionTone(a.kind)}>{labelOf('attention_kind', a.kind)}</Badge>
                    <span className="truncate font-mono text-xs text-muted-foreground">{a.spec ?? '–'}</span>
                  </li>
                ))}
                {hidden > 0 ? <li className="text-xs text-muted-foreground">+{hidden} weitere</li> : null}
              </ul>
            ) : null}
          </>
        ) : null}

        {project.warnings.length > 0 ? (
          <ul className="flex flex-wrap gap-1.5" aria-label="Warnungen">
            {project.warnings.map((w) => (
              <li key={w}>
                <Badge variant="warning">
                  {w === 'no_push_24h' ? <WifiOff /> : <Clock />}
                  {WARNING_TEXT[w]}
                </Badge>
              </li>
            ))}
          </ul>
        ) : null}

        <div className="mt-auto flex flex-wrap items-end justify-between gap-x-3 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
          <div className="grid gap-0.5">
            {marker ? (
              <p className="inline-flex items-center gap-1" title={fmtDateTime(marker.ts)} data-testid="last-marker">
                <Rocket className="size-3" />
                {labelOf('marker_kind', marker.kind)} {fmtRelative(marker.ts, now)}
                {marker.specs.length > 0 ? ` · ${marker.specs.map(specNumber).join(', ')}` : ''}
              </p>
            ) : null}
            <p title={fmtDateTime(project.last_activity)}>Letzte Aktivität: {fmtRelative(project.last_activity, now)}</p>
          </div>
          <span
            className="inline-flex items-center gap-1 font-medium opacity-0 transition-opacity group-hover:opacity-100 group-has-[a[data-card-link]:focus-visible]:opacity-100"
            aria-hidden
            data-testid="open-hint"
          >
            Board öffnen <ArrowRight className="size-3 transition-transform group-hover:translate-x-0.5" />
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
