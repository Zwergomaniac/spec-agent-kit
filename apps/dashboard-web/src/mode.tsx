import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { api } from './api'

/** Lokaler Modus (`sak board serve`): ein Projekt, kein Portfolio, kein Admin, kein Login (Spec 010 FR-001). */
export interface LocalInfo {
  projectKey: string
}

/** Erkennt den lokalen Modus ausschließlich über `/api/meta` (`mode: "local"` und `project_key`). */
export async function detectLocal(): Promise<LocalInfo | null> {
  try {
    const meta = await api.meta()
    if (meta.mode === 'local' && typeof meta.project_key === 'string' && meta.project_key !== '') return { projectKey: meta.project_key }
  } catch {
    // Online (401) oder nicht erreichbar: kein lokaler Modus.
  }
  return null
}

interface ModeValue {
  local: LocalInfo | null
  projectName: string | null
  setProjectName: (name: string) => void
}

const ModeContext = createContext<ModeValue>({ local: null, projectName: null, setProjectName: () => {} })

export function ModeProvider({ local, children }: { local: LocalInfo | null; children: ReactNode }) {
  const [projectName, setProjectName] = useState<string | null>(null)
  const value = useMemo(() => ({ local, projectName, setProjectName }), [local, projectName])
  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>
}

export function useMode(): ModeValue {
  return useContext(ModeContext)
}
