import type { ReactNode } from 'react'
import { Tip } from '@/components/Tip'
import { cn } from '@/lib/utils'

/** Eine Board-Spalte. Die Breite bestimmt das Board-Grid; die Spalte selbst schrumpft (min-w-0) und bricht Inhalt um. */
export function StageColumn({
  id,
  title,
  count,
  highlight = false,
  definition,
  children
}: {
  id: string
  title: string
  count: number
  highlight?: boolean
  /** Definition für den Tooltip der Spaltenüberschrift (Spec 010 FR-004). */
  definition?: string
  children: ReactNode
}) {
  const headingId = `col-${id}`
  return (
    <section
      aria-labelledby={headingId}
      data-testid={`column-${id}`}
      className={cn('flex min-w-0 flex-col rounded-xl border bg-muted/40 p-2 min-[1536px]:p-3', highlight && 'border-warning/50 bg-warning-soft/40')}
    >
      <h3 id={headingId} className="mb-3 flex items-center justify-between gap-2 text-sm font-semibold">
        <span className="min-w-0 break-words">
          {definition ? (
            <Tip content={definition} className="underline decoration-muted-foreground/50 decoration-1 underline-offset-4" testId={`head-tip-${id}`}>
              {title}
            </Tip>
          ) : (
            title
          )}
        </span>
        <span className="shrink-0 rounded-md bg-background px-1.5 py-0.5 text-xs font-medium text-muted-foreground tabular-nums">{count}</span>
      </h3>
      {count === 0 ? <p className="py-2 text-xs text-muted-foreground">Leer</p> : children}
    </section>
  )
}
