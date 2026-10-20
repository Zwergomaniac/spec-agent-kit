// Screenshot-Smoke-Test des Pilot-Boards (SC-004) bei 1440x900 und 390x844.
// Die Screenshots landen in e2e/screenshots/ (nicht eingecheckt).
import { expect, test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { PILOT_KEY, PILOT_RUN, pilotBoard } from './fixtures'
import { apiLogin } from './helpers'

const SHOTS = fileURLToPath(new URL('./screenshots/', import.meta.url))
const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 }
] as const

const board = pilotBoard()

async function shot(page: Page, name: string, viewport: string): Promise<void> {
  mkdirSync(SHOTS, { recursive: true })
  await page.screenshot({ path: `${SHOTS}${name}-${viewport}.png`, fullPage: true })
}

async function settle(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle')
  // Recharts misst erst nach dem Layout.
  await page.waitForTimeout(300)
}

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow, 'Seite darf nicht horizontal scrollen').toBeLessThanOrEqual(0)
}

for (const vp of VIEWPORTS) {
  test.describe(`Pilot-Board ${vp.name} ${vp.width}x${vp.height}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } })

    test.beforeEach(async ({ context }) => {
      await apiLogin(context)
    })

    test('Portfolio zeigt zwei Karten, die eskalierte hervorgehoben', async ({ page }) => {
      await page.goto('/#/portfolio')
      const card = page.getByTestId(`project-card-${PILOT_KEY}`)
      await expect(card).toBeVisible()
      await expect(card).toHaveAttribute('data-escalated', 'true')
      await expect(card.getByText('Rundenlimit erreicht, offene Muss-Befunde')).toBeVisible()
      await expect(card.getByRole('link', { name: new RegExp(PILOT_RUN) })).toHaveAttribute('href', `#/run/${PILOT_KEY}/${PILOT_RUN}`)
      await expect(page.getByTestId('project-card-spec-agent-kit')).toBeVisible()
      await expect(page.getByTestId('last-updated')).toContainText('Zuletzt aktualisiert')
      await settle(page)
      await expectNoHorizontalOverflow(page)
      await shot(page, 'portfolio', vp.name)
    })

    test('Projekt-Board stellt das Pilot-Board vollständig dar', async ({ page }) => {
      await page.goto(`/#/project/${PILOT_KEY}`)
      await expect(page.getByRole('heading', { level: 1, name: 'ImmoAgent' })).toBeVisible()

      // Kennzahlen
      await expect(page.getByTestId('kpi-in_progress')).toContainText(String(board.metrics.in_progress))
      await expect(page.getByTestId('kpi-done')).toContainText(String(board.metrics.done))
      await expect(page.getByTestId('kpi-blocked')).toContainText(String(board.metrics.blocked))
      await expect(page.getByTestId('kpi-waiting')).toContainText(String(board.metrics.waiting))
      await expect(page.getByTestId('kpi-lead')).toContainText('3,5')

      // Jede nicht zurückgestellte Spec steht in genau einer Stationsspalte, die zurückgestellte unter „Zurückgestellt“.
      for (const spec of board.specs.filter((s) => !s.descoped)) {
        const card = page.getByTestId(`spec-${spec.number}`)
        await expect(card, `Spec ${spec.dir}`).toBeVisible()
        await expect(card).toContainText(spec.title)
        await expect(page.getByTestId(`column-${spec.stage}`).getByTestId(`spec-${spec.number}`)).toBeVisible()
      }
      await expect(page.getByTestId('descoped')).toContainText('Altes Feature')

      // „Mensch prüft / entscheidet“ und Agenten-Panel
      await expect(page.getByTestId('column-human').getByTestId('attention-item')).toHaveCount(board.attention.length)
      await expect(page.getByTestId('run-panel')).toContainText('Eskaliert')
      await expect(page.getByTestId('run-panel')).toContainText('Rundenlimit erreicht')

      // Ticker und Diagramme
      await expect(page.getByTestId('ticker')).toContainText('feat(088): Kartenlayer umschalten')
      await expect(page.getByTestId('chart-lead-time')).toBeVisible()
      await expect(page.getByTestId('chart-verdicts')).toBeVisible()
      await expect(page.getByText('Datei specs/075-altes-feature/tasks.md nicht lesbar')).toBeVisible()

      // Layout: ab 900 px nebeneinander, darunter untereinander
      const human = await page.getByTestId('column-human').boundingBox()
      const specified = await page.getByTestId('column-specified').boundingBox()
      expect(human && specified).toBeTruthy()
      if (vp.width >= 900) expect(Math.abs(human!.y - specified!.y)).toBeLessThan(4)
      else {
        expect(specified!.y).toBeGreaterThan(human!.y + human!.height - 1)
        expect(Math.abs(human!.x - specified!.x)).toBeLessThan(4)
      }

      await settle(page)
      await expectNoHorizontalOverflow(page)
      await shot(page, 'project-board', vp.name)
    })

    test('Läufe, Aufmerksamkeit und Konflikte', async ({ page }) => {
      await page.goto(`/#/project/${PILOT_KEY}?tab=runs`)
      for (const run of board.runs) await expect(page.getByTestId(`run-row-${run.run_id}`)).toBeVisible()
      await expectNoHorizontalOverflow(page)
      await shot(page, 'project-runs', vp.name)

      await page.goto(`/#/project/${PILOT_KEY}?tab=attention`)
      await expect(page.getByTestId('attention-row')).toHaveCount(board.attention.length)
      await shot(page, 'project-attention', vp.name)

      await page.goto(`/#/project/${PILOT_KEY}?tab=conflicts`)
      await expect(page.getByText('Konflikte kommen mit dem Parallelbetrieb')).toBeVisible()
      await shot(page, 'project-conflicts', vp.name)
    })

    test('Lauf-Ansicht zeigt Runden, Eskalation und Event-Log', async ({ page }) => {
      await page.goto(`/#/run/${PILOT_KEY}/${PILOT_RUN}`)
      const run = board.runs.find((r) => r.run_id === PILOT_RUN)!
      await expect(page.getByTestId('round-1')).toBeVisible()
      await expect(page.getByTestId('round-2')).toBeVisible()
      await expect(page.getByTestId('escalations')).toContainText('Rundenlimit')
      await expect(page.getByTestId('timeline')).toContainText('Lauf eskaliert')
      expect(await page.getByTestId('event-row').count()).toBeGreaterThanOrEqual(run.stations.length)
      await settle(page)
      await expectNoHorizontalOverflow(page)
      await shot(page, 'run', vp.name)
    })

    test('Admin', async ({ page }) => {
      await page.goto('/#/admin')
      await expect(page.getByTestId(`admin-row-${PILOT_KEY}`)).toBeVisible()
      await expectNoHorizontalOverflow(page)
      await shot(page, 'admin', vp.name)
    })
  })
}

test.describe('Dark Mode', () => {
  test.use({ viewport: { width: 1440, height: 900 }, colorScheme: 'dark' })

  test('folgt dem System und lässt sich umschalten', async ({ context, page }) => {
    await apiLogin(context)
    await page.goto(`/#/project/${PILOT_KEY}`)
    await expect(page.locator('html')).toHaveClass(/dark/)
    await expect(page.getByTestId('chart-verdicts')).toBeVisible()
    await settle(page)
    await shot(page, 'project-board-dark', 'desktop')

    // System -> Hell
    await page.getByRole('button', { name: /Darstellung/ }).click()
    await expect(page.locator('html')).not.toHaveClass(/dark/)
    // Hell -> Dunkel
    await page.getByRole('button', { name: /Darstellung/ }).click()
    await expect(page.locator('html')).toHaveClass(/dark/)
  })
})

test('Tastatur: Tabs sind per Pfeiltasten bedienbar', async ({ context, page }) => {
  await apiLogin(context)
  await page.goto(`/#/project/${PILOT_KEY}`)
  await page.getByRole('tab', { name: 'Board' }).focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: 'Läufe' })).toBeFocused()
})
