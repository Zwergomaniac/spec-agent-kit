import { GitMerge } from 'lucide-react'
import { EmptyState } from '@/components/states'

/** In v1 gibt es keine Konfliktdaten: ehrlicher Hinweis statt leerer Liste (Spec 007, User Story 2). */
export function ConflictsTab() {
  return (
    <EmptyState title="Konflikte kommen mit dem Parallelbetrieb" icon={<GitMerge />}>
      Konflikte zwischen gleichzeitig laufenden Läufen werden erst erfasst, wenn das Kit parallele Läufe unterstützt. In dieser Version liegen dazu keine Daten vor.
    </EmptyState>
  )
}
