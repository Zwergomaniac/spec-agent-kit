// Erzeugt den scrypt-Hash für SAK_ADMIN_PASSWORD_HASH.
// Das Passwort kommt interaktiv (ohne Echo) oder über stdin, nie über Argumente (Shell-History).
//   Container: docker exec -it spec-agent-dashboard node dist/cli/hash-password.js
//   Pipe:      echo -n 'geheim' | node dist/cli/hash-password.js
import { hashPassword } from '../auth/password.js'
import { readHidden, readStdin } from './prompt.js'

async function main(): Promise<void> {
  let password: string
  if (process.stdin.isTTY) {
    password = await readHidden('Neues Admin-Passwort: ')
    const again = await readHidden('Wiederholen: ')
    if (password !== again) throw new Error('Die Eingaben stimmen nicht überein.')
  } else {
    password = await readStdin()
  }
  if (password.length < 12) throw new Error('Das Passwort muss mindestens 12 Zeichen lang sein.')
  process.stdout.write(`${await hashPassword(password)}\n`)
}

main().catch((err: unknown) => {
  process.stderr.write(`Fehler: ${err instanceof Error ? err.message : String(err)}\n`)
  process.exit(1)
})
