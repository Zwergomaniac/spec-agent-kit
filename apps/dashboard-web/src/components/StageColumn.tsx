import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** Eine Board-Spalte. Ab 900 px nebeneinander mit festem Mindestmaß, darunter untereinander. */
export function StageColumn({
  id,
  title,
  count,
  highlight = false,
  children
}: {
  id: string
  title: string
  count: number
  highlight?: boolean
  children: ReactNode
}) {
  const headingId = `col-${id}`
  return (
    <section
      aria-labelledby={headingId}
      data-testid={`column-${id}`}
      className={cn('flex min-w-0 flex-col rounded-xl border bg-muted/40 p-3', highlight && 'border-warning/50 bg-warning-soft/40')}
    >
      <h3 id={headingId} className="mb-3 flex items-center justify-between gap-2 text-sm font-semibold">
        <span>{title}</span>
        <span className="rounded-md bg-background px-1.5 py-0.5 text-xs font-medium text-muted-foreground tabular-nums">{count}</span>
      </h3>
      {count === 0 ? <p className="py-2 text-xs text-muted-foreground">Leer</p> : children}
    </section>
  )
}
