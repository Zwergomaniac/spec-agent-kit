// Öffentliche Schnittstelle von @sak/contracts. Quelle der Wahrheit ist schema/ (JSON Schema).
// src/generated/ wird von scripts/gen-zod.mjs erzeugt und nie von Hand geändert.
import { labels, type Locale } from './generated/labels'
import type { VocabularyLevel } from './generated/vocabulary'

export * from './generated/zod'
export * from './generated/vocabulary'
export * from './generated/labels'
export * from './generated/limits'
export * from './deep-links'

/**
 * Anzeigebezeichnung eines Vokabular-Werts in der Locale (Default `de`).
 * Unbekannte Werte werden unverändert zurückgegeben (Spec 001, Randfall "unbekannter Wert von außen").
 */
export function label(level: VocabularyLevel, value: string, locale: Locale = 'de'): string {
  const table = labels[locale][level] as Record<string, string>
  return table[value] ?? value
}
