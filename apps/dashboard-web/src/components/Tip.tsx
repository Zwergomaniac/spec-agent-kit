import { createElement, useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ElementType, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'

// Immer nur ein Tooltip gleichzeitig: Ein neu geöffneter schließt den vorherigen sofort.
let closeActive: (() => void) | null = null

const GAP = 6
const MARGIN = 8

/**
 * Tooltip, der per Maus (Hover) und Tastatur (Fokus) erreichbar ist. Escape schließt ihn,
 * der Mauszeiger darf auf das Popover wechseln. Das Popover liegt per Portal im body, damit
 * scrollende Container (Ticker) es nicht abschneiden.
 */
export function Tip({
  content,
  children,
  as = 'span',
  className,
  testId
}: {
  content: ReactNode
  children: ReactNode
  as?: ElementType
  className?: string
  testId?: string
}) {
  const id = useId()
  const triggerRef = useRef<HTMLElement>(null)
  const popRef = useRef<HTMLDivElement>(null)
  const timer = useRef<number | undefined>(undefined)
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)

  const close = useCallback((): void => {
    window.clearTimeout(timer.current)
    setOpen(false)
  }, [])

  const show = (): void => {
    window.clearTimeout(timer.current)
    if (closeActive && closeActive !== close) closeActive()
    closeActive = close
    setOpen(true)
  }
  const hide = (): void => {
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setOpen(false), 120)
  }

  useEffect(
    () => () => {
      window.clearTimeout(timer.current)
      if (closeActive === close) closeActive = null
    },
    [close]
  )

  // Position unter (oder bei Platzmangel über) dem Auslöser; bleibt beim Scrollen und Ändern der Fenstergröße am Auslöser.
  const place = useCallback((): void => {
    const trigger = triggerRef.current
    const pop = popRef.current
    if (!trigger || !pop) return
    const t = trigger.getBoundingClientRect()
    const w = pop.offsetWidth
    const h = pop.offsetHeight
    const vw = document.documentElement.clientWidth
    const vh = window.innerHeight
    let top = t.bottom + GAP
    if (top + h > vh - MARGIN && t.top - GAP - h >= MARGIN) top = t.top - GAP - h
    const left = Math.max(MARGIN, Math.min(t.left, vw - w - MARGIN))
    setPos({ left, top })
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    return () => {
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
    }
  }, [open, place])

  useLayoutEffect(() => {
    if (!open) {
      setPos(null)
      return
    }
    place()
  }, [open, place])

  return (
    <>
      {createElement(
        as,
        {
          ref: triggerRef,
          tabIndex: 0,
          className: cn('rounded-sm', className),
          'aria-describedby': open ? id : undefined,
          'data-testid': testId,
          onMouseEnter: show,
          onMouseLeave: hide,
          onFocus: show,
          onBlur: hide
        },
        children
      )}
      {open
        ? createPortal(
            <div
              ref={popRef}
              id={id}
              role="tooltip"
              data-testid="tip"
              onMouseEnter={show}
              onMouseLeave={hide}
              style={{ position: 'fixed', left: pos?.left ?? 0, top: pos?.top ?? 0, visibility: pos ? 'visible' : 'hidden' }}
              className="z-50 w-max max-w-[min(22rem,calc(100vw-1rem))] rounded-md border bg-popover px-3 py-2 text-xs leading-snug text-popover-foreground shadow-md"
            >
              {content}
            </div>,
            document.body
          )
        : null}
    </>
  )
}
