const dateTime = new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'short' })
const dateTimeZone = new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium', timeStyle: 'long' })
const timeOnly =new Intl.DateTimeFormat('de-DE', { timeStyle: 'medium' })
const dateOnly = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit' })

function valid(iso: string | null | undefined): iso is string {
  return !!iso && !Number.isNaN(Date.parse(iso))
}

export function fmtDateTime(iso: string | null | undefined): string {
  return valid(iso) ? dateTime.format(new Date(iso)) : '–'
}

/** Lokale Zeit mit Zeitzone, z. B. „21.10.2026, 11:30:15 MESZ“. */
export function fmtDateTimeZone(iso: string | null | undefined): string {
  return valid(iso) ? dateTimeZone.format(new Date(iso)) : '–'
}

export function fmtTime(ms: number): string {
  return timeOnly.format(new Date(ms))
}

export function fmtShortDate(iso: string | null | undefined): string {
  return valid(iso) ? dateOnly.format(new Date(iso)) : '–'
}

/** Relative Angabe wie "vor 5 Min."; ältere Werte werden zum Datum. */
export function fmtRelative(iso: string | null | undefined, nowMs: number = Date.now()): string {
  if (!valid(iso)) return '–'
  const diff = Math.round((nowMs - Date.parse(iso)) / 1000)
  if (diff < 45) return 'gerade eben'
  if (diff < 90 * 60) return `vor ${Math.max(1, Math.round(diff / 60))} Min.`
  if (diff < 36 * 3600) return `vor ${Math.round(diff / 3600)} Std.`
  if (diff < 14 * 86400) return `vor ${Math.round(diff / 86400)} Tagen`
  return fmtDateTime(iso)
}

/** Sekunden als "21 Min." oder "1 Std. 5 Min.". */
export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '–'
  if (seconds < 60) return `${Math.round(seconds)} Sek.`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} Min.`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m === 0 ? `${h} Std.` : `${h} Std. ${m} Min.`
}

export function fmtDays(days: number | null | undefined): string {
  if (days === null || days === undefined) return '–'
  return `${days.toLocaleString('de-DE', { maximumFractionDigits: 1 })} Tage`
}

export function specNumber(n: number): string {
  return `#${String(n).padStart(3, '0')}`
}
