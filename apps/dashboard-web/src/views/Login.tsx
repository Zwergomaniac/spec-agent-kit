import { Lock } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { ApiError } from '@/api'
import { useAuth } from '@/auth'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

function messageFor(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return 'Das Passwort ist nicht korrekt.'
    if (err.status === 429) {
      const seconds = typeof err.body.retry_after_s === 'number' ? err.body.retry_after_s : 900
      return `Zu viele Fehlversuche. Bitte in ${Math.max(1, Math.ceil(seconds / 60))} Min. erneut versuchen.`
    }
    if (err.status === 0) return 'Der Server ist nicht erreichbar.'
  }
  return 'Die Anmeldung ist fehlgeschlagen.'
}

/** Anmeldung. Die URL bleibt unverändert, daher landet der Betreiber nach dem Login direkt auf dem Ziel (US1.2). */
export function Login({ onSuccess }: { onSuccess?: () => void }) {
  const { login } = useAuth()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent): Promise<void> {
    e.preventDefault()
    if (busy || !password) return
    setBusy(true)
    setError(null)
    try {
      await login(password)
      setPassword('')
      onSuccess?.()
    } catch (err) {
      setError(messageFor(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] w-full max-w-sm items-center">
      <Card className="w-full">
        <CardHeader>
          <div className="mb-2 flex size-9 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
            <Lock className="size-4" />
          </div>
          <CardTitle className="text-xl">Anmelden</CardTitle>
          <CardDescription>Spec Agent Dashboard. Zugang nur für den Betreiber.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="password">Passwort</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                autoFocus
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? 'login-error' : undefined}
              />
            </div>
            {error ? (
              <Alert variant="destructive">
                <AlertDescription id="login-error">{error}</AlertDescription>
              </Alert>
            ) : null}
            <Button type="submit" disabled={busy || !password}>
              {busy ? 'Anmelden …' : 'Anmelden'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
