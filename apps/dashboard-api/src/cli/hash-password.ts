// Erzeugt den scrypt-Hash für SAK_ADMIN_PASSWORD_HASH.
// Das Passwort kommt interaktiv (ohne Echo) oder über stdin, nie über Argumente (Shell-History).
//   Container: docker exec -it spec-agent-dashboard node dist/cli/hash-password.js
//   Pipe:      echo -n 'geheim' | node dist/cli/hash-password.js
import { hashPassword } from '../auth/password.js'

async function readHidden(prompt: string): Promise<string> {
  process.stderr.write(prompt)
  const stdin = process.stdin
  stdin.setRawMode(true)
  stdin.resume()
  stdin.setEncoding('utf8')
  return new Promise((resolve, reject) => {
    let value = ''
    const onData = (chunk: string): void => {
      for (const ch of chunk) {
        if (ch === '\r' || ch === '\n') {
          stdin.setRawMode(false)
          stdin.pause()
          stdin.off('data', onData)
          process.stderr.write('\n')
          resolve(value)
          return
        }
        if (ch === '\u0003') {
          stdin.setRawMode(false)
          reject(new Error('Abgebrochen.'))
          return
        }
        if (ch === '\u007f' || ch === '\b') value = value.slice(0, -1)
        else value += ch
      }
    }
    stdin.on('data', onData)
  })
}

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = []
  for await (const chunk of process.stdin) chunks.push(chunk as Buffer)
  return Buffer.concat(chunks).toString('utf8').replace(/\r?\n$/, '')
}

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
