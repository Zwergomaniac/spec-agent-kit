// Projektverwaltung für den Betrieb im Container (Spec 007, User Story 5).
//   node dist/cli/project.js add <key> <name...>
//   node dist/cli/project.js list
//   node dist/cli/project.js rotate <key>
//   node dist/cli/project.js remove <key>
// Der Projekt-Schlüssel wird genau einmal ausgegeben (add, rotate).
import { openDb } from '../db.js'
import { ProjectError, createProject, listProjects, removeProject, rotateProjectToken } from '../services/projects.js'

function usage(): never {
  process.stderr.write('Aufruf: project <add <key> <name>|list|rotate <key>|remove <key>>\n')
  process.exit(2)
}

function main(): void {
  const [command, ...rest] = process.argv.slice(2)
  const dbPath = process.env.SAK_DB_PATH || '/data/dashboard.db'
  const db = openDb(dbPath)
  try {
    switch (command) {
      case 'add': {
        const [key, ...nameParts] = rest
        if (!key || nameParts.length === 0) usage()
        const { project, token } = createProject(db, key, nameParts.join(' '))
        process.stdout.write(`Projekt ${project.key} angelegt.\nProjekt-Schlüssel (wird nur jetzt angezeigt):\n${token}\n`)
        break
      }
      case 'list': {
        for (const p of listProjects(db)) {
          process.stdout.write(`${p.key}\t${p.name}\tletzte Einlieferung: ${p.last_ingest_at ?? '-'}\n`)
        }
        break
      }
      case 'rotate': {
        const [key] = rest
        if (!key) usage()
        const { token } = rotateProjectToken(db, key)
        process.stdout.write(`Neuer Projekt-Schlüssel für ${key} (wird nur jetzt angezeigt):\n${token}\n`)
        break
      }
      case 'remove': {
        const [key] = rest
        if (!key) usage()
        removeProject(db, key)
        process.stdout.write(`Projekt ${key} entfernt.\n`)
        break
      }
      default:
        usage()
    }
  } catch (err) {
    if (err instanceof ProjectError) {
      process.stderr.write(`Fehler: ${err.message}\n`)
      process.exit(1)
    }
    throw err
  } finally {
    db.close()
  }
}

main()
