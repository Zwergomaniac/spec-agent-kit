import fs from 'node:fs'
import path from 'node:path'

const projectName = process.argv[2] || 'example-project'
const targetDir = process.argv[3] || path.join(process.cwd(), 'output-init', projectName)
const base = path.join(process.cwd(), 'packages', 'agent-blueprint', 'templates', 'root')
fs.mkdirSync(targetDir, { recursive: true })
function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true })
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name)
    const d = path.join(dest, entry.name)
    if (entry.isDirectory()) copyDir(s, d)
    else fs.writeFileSync(d, fs.readFileSync(s, 'utf8').replaceAll('__PROJECT_KEY__', projectName), 'utf8')
  }
}
copyDir(base, targetDir)
console.log(`Initialized ${projectName} in ${targetDir}`)
