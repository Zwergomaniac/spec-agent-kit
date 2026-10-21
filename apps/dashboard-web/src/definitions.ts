// Zentrale Definitionen für Tooltips (Spec 010 FR-004). Die Texte entsprechen Spec 001 FR-006,
// Spec 006 FR-003/FR-006 und Spec 010 (Clarifications zu „Fertig“ und `[~]`).

export type KpiId = 'in_progress' | 'waiting' | 'blocked' | 'done' | 'lead'

export const KPI_DEFINITIONS: Record<KpiId, string> = {
  in_progress:
    'In Arbeit = Station Umsetzung: mindestens eine Task erledigt, aber noch nicht alle. Auch Specs ab „Umsetzung fertig“ mit offenen oder teilweise erledigten Tasks zählen hier.',
  waiting:
    'Wartet auf Mensch = Anzahl der Einträge in der Spalte „Mensch prüft / entscheidet“, etwa Freigabe, Klärung, Eskalation oder Betreiber-Aufgabe.',
  blocked:
    'Blockiert = Specs mit einem offenen Blocker. Blocker liefert das Plugin legacy-status aus blockers.yml. Ohne dieses Plugin ist der Wert 0.',
  done: 'Fertig = Station „Umsetzung fertig“ oder höher (Deploy, Live geprüft) und keine offene oder teilweise erledigte Task. Specs mit offenen Tasks zählen als „In Arbeit“.',
  lead: 'Ø Durchlaufzeit = Mittelwert der Zeit vom ersten Spec-Commit bis zum Abschluss, in Tagen.'
}

export const APPROVAL_DEFINITION = 'Freigabe = Taskliste vorhanden, keine Task erledigt, nie ein Lauf gestartet.'

export const HUMAN_COLUMN_DEFINITION =
  'Mensch prüft / entscheidet = Einträge, die auf eine Person warten: Freigabe (Taskliste vorhanden, keine Task erledigt, nie ein Lauf gestartet), Klärung, Eskalation, verwaister Lauf, Betreiber-Aufgabe, Blocker, Entscheidung.'

export const STAGE_DEFINITIONS: Record<string, string> = {
  specified: 'Spec = Spec-Dokument vorhanden.',
  clarified: 'Klärung = Die Spec enthält einen Klärungsabschnitt.',
  planned: 'Plan = Plan vorhanden.',
  tasked: `Tasks = Taskliste vorhanden. ${APPROVAL_DEFINITION}`,
  implementing: 'Umsetzung = Mindestens eine Task erledigt, aber noch nicht alle.',
  implemented: 'Umsetzung fertig = Alle Tasks erledigt (mindestens eine).',
  deployed: 'Deploy = Deploy-Marker nach dem letzten Task-Commit. Bei offenen Tasks bleibt die Station, die Spec zählt aber nicht als „Fertig“.',
  verified: 'Live geprüft = Verified-Marker im Commit-Betreff.'
}

export function stageDefinition(stage: string): string | undefined {
  return STAGE_DEFINITIONS[stage]
}
