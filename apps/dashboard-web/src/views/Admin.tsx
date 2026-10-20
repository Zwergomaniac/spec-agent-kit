import { Check, Copy, KeyRound, Plus, RotateCw, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { api, ApiError } from '@/api'
import { EmptyState, ErrorState, LastUpdated, LoadingView, PageHeader } from '@/components/states'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { fmtDateTime, fmtRelative } from '@/format'
import { usePolled } from '@/hooks'
import { safeLink, links } from '@/router'

interface Reveal {
  key: string
  token: string
  action: 'created' | 'rotated'
}

function createError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) return 'Dieser Projektschlüssel existiert bereits.'
    if (err.status === 400) return typeof err.body.message === 'string' ? err.body.message : 'Die Eingabe ist ungültig.'
  }
  return 'Das Projekt konnte nicht angelegt werden.'
}

function TokenReveal({ reveal, onDismiss }: { reveal: Reveal; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false)
  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(reveal.token)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <Alert variant="warning" data-testid="token-reveal">
      <KeyRound />
      <AlertTitle>
        {reveal.action === 'created' ? 'Projekt angelegt' : 'Schlüssel erneuert'}: {reveal.key}
      </AlertTitle>
      <AlertDescription>
        <p>Dieser Projekt-Schlüssel wird nur jetzt angezeigt. Trage ihn im Zielprojekt ein und speichere ihn sicher.</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <code className="rounded-md border bg-card px-2 py-1 font-mono text-xs break-all text-foreground" data-testid="token-value">
            {reveal.token}
          </code>
          <Button type="button" variant="outline" size="sm" className="text-foreground" onClick={copy}>
            {copied ? <Check /> : <Copy />} {copied ? 'Kopiert' : 'Kopieren'}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={onDismiss}>
            Schließen
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  )
}

export function Admin() {
  const { data, error, updatedAt, refresh } = usePolled(api.adminProjects, 'admin')
  const [key, setKey] = useState('')
  const [name, setName] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [reveal, setReveal] = useState<Reveal | null>(null)
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  async function create(e: FormEvent): Promise<void> {
    e.preventDefault()
    setBusy(true)
    setFormError(null)
    try {
      const res = await api.adminCreate(key.trim(), name.trim())
      setReveal({ key: res.project.key, token: res.token, action: 'created' })
      setKey('')
      setName('')
      refresh()
    } catch (err) {
      setFormError(createError(err))
    } finally {
      setBusy(false)
    }
  }

  async function rotate(projectKey: string): Promise<void> {
    setActionError(null)
    try {
      const res = await api.adminRotate(projectKey)
      setReveal({ key: projectKey, token: res.token, action: 'rotated' })
    } catch {
      setActionError('Der Schlüssel konnte nicht erneuert werden.')
    }
  }

  async function remove(projectKey: string): Promise<void> {
    setActionError(null)
    try {
      await api.adminRemove(projectKey)
      setConfirmRemove(null)
      if (reveal?.key === projectKey) setReveal(null)
      refresh()
    } catch {
      setActionError('Das Projekt konnte nicht entfernt werden.')
    }
  }

  return (
    <>
      <PageHeader
        title="Admin"
        subtitle="Projekte verwalten und Projekt-Schlüssel ausgeben."
        actions={<LastUpdated updatedAt={updatedAt} error={error} onRefresh={refresh} />}
      />

      <div className="grid grid-cols-1 gap-6">
        {reveal ? <TokenReveal reveal={reveal} onDismiss={() => setReveal(null)} /> : null}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Projekt anlegen</CardTitle>
            <CardDescription>Der Schlüssel besteht aus 2 bis 40 Zeichen: Kleinbuchstaben, Ziffern und Bindestrich.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={create} className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
              <div className="grid gap-2">
                <Label htmlFor="project-key">Projektschlüssel</Label>
                <Input id="project-key" value={key} onChange={(e) => setKey(e.target.value)} placeholder="immo-agent" autoComplete="off" required maxLength={40} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="project-name">Name</Label>
                <Input id="project-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="ImmoAgent" autoComplete="off" required maxLength={100} />
              </div>
              <Button type="submit" disabled={busy || !key || !name}>
                <Plus /> Anlegen
              </Button>
            </form>
            {formError ? (
              <Alert variant="destructive" className="mt-4">
                <AlertDescription>{formError}</AlertDescription>
              </Alert>
            ) : null}
          </CardContent>
        </Card>

        {actionError ? (
          <Alert variant="destructive">
            <AlertDescription>{actionError}</AlertDescription>
          </Alert>
        ) : null}

        {error && !data ? <ErrorState error={error} onRetry={refresh} /> : null}
        {!data && !error ? <LoadingView rows={2} /> : null}
        {data && data.projects.length === 0 ? <EmptyState title="Noch keine Projekte">Lege oben das erste Projekt an.</EmptyState> : null}

        {data && data.projects.length > 0 ? (
          <div className="rounded-xl border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Schlüssel</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Angelegt</TableHead>
                  <TableHead>Letzte Einlieferung</TableHead>
                  <TableHead className="text-right">Aktionen</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.projects.map((p) => (
                  <TableRow key={p.key} data-testid={`admin-row-${p.key}`}>
                    <TableCell className="font-mono text-xs">
                      <a href={safeLink(() => links.project(p.key))} className="underline-offset-2 hover:underline">
                        {p.key}
                      </a>
                    </TableCell>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell className="whitespace-nowrap text-muted-foreground">{fmtDateTime(p.created_at)}</TableCell>
                    <TableCell className="whitespace-nowrap text-muted-foreground" title={fmtDateTime(p.last_ingest_at)}>
                      {p.last_ingest_at ? fmtRelative(p.last_ingest_at) : 'noch nie'}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-2">
                        {confirmRemove === p.key ? (
                          <>
                            <Button size="sm" variant="destructive" onClick={() => remove(p.key)}>
                              Wirklich entfernen
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setConfirmRemove(null)}>
                              Abbrechen
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button size="sm" variant="outline" onClick={() => rotate(p.key)} aria-label={`Schlüssel von ${p.key} erneuern`}>
                              <RotateCw /> Erneuern
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setConfirmRemove(p.key)} aria-label={`${p.key} entfernen`}>
                              <Trash2 /> Entfernen
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </div>
    </>
  )
}
