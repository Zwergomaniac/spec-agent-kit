// Lokaler Modus (Spec 010 B06): Die in board/web/ eingecheckte UI läuft gegen einen Mock von `sak board serve`.
// Der Screenshot-Vergleich lokal ↔ online (SC-001) nutzt dieselben Board-Daten. Screenshots: e2e/screenshots/.
import { expect, test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { PILOT_KEY, PILOT_RUN, pilotBoard, pilotEvents } from './fixtures'
import { apiLogin } from './helpers'
import { startMockBoardServer, type MockBoardServer } from './mock-board-server'

const SHOTS = fileURLToPath(new URL('./screenshots/', import.meta.url))
const FIXED_NOW = new Date('2026-10-21T10:00:00+02:00')

const board = pilotBoard()
const events = pilotEvents(board)
let mock: MockBoardServer

test.beforeAll(async () => {
  mkdirSync(SHOTS, { recursive: true })
  mock = await startMockBoardServer(board, events)
})
test.afterAll(async () => {
  await mock.close()
})

test.use({ viewport: { width: 1920, height: 1080 } })

async function openLocal(page: Page, hash = ''): Promise<void> {
  await page.clock.setFixedTime(FIXED_NOW)
  await page.goto(`${mock.url}/${hash}`)
  await page.waitForLoadState('networkidle')
}

async function settle(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(300)
}

/** Fokussiert per Tab das erste Element, auf das `predicate` passt (max. 120 Tab-Schritte). */
async function tabTo(page: Page, testId: string): Promise<void> {
  for (let i = 0; i < 120; i++) {
    await page.keyboard.press('Tab')
    const hit = await page.evaluate((id) => document.activeElement?.getAttribute('data-testid') === id, testId)
    if (hit) return
  }
  throw new Error(`Per Tab nicht erreichbar: ${testId}`)
}

/** Kontrastverhältnis (WCAG) von Text und Hintergrund des Tooltips. */
async function tooltipContrast(page: Page): Promise<number> {
  return page.evaluate(() => {
    const tip = document.querySelector<HTMLElement>('[data-testid="tip"]')!
    const rgb = (css: string): number[] => {
      const c = document.createElement('canvas').getContext('2d')!
      c.clearRect(0, 0, 1, 1)
      c.fillStyle = css
      c.fillRect(0, 0, 1, 1)
      return Array.from(c.getImageData(0, 0, 1, 1).data.slice(0, 3))
    }
    const lum = ([r, g, b]: number[]): number => {
      const f = (v: number): number => {
        const s = v! / 255
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
      }
      return 0.2126 * f(r!) + 0.7152 * f(g!) + 0.0722 * f(b!)
    }
    const style = getComputedStyle(tip)
    const a = lum(rgb(style.color))
    const b = lum(rgb(style.backgroundColor))
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
  })
}

test.describe('Lokaler Modus', () => {
  test('startet auf der Projektansicht ohne Portfolio, Admin, Login und Auth-Aufrufe', async ({ page }) => {
    await openLocal(page)
    expect(new URL(page.url()).hash).toBe(`#/project/${PILOT_KEY}`)
    await expect(page.getByTestId('local-indicator')).toContainText('Lokal')
    await expect(page.getByTestId('local-indicator')).toContainText('ImmoAgent')
    await expect(page.getByRole('link', { name: 'Portfolio' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Admin' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Abmelden' })).toHaveCount(0)
    await expect(page.getByRole('tab', { name: 'Board', selected: true })).toBeVisible()
    expect(mock.requests).toContain('/api/meta')
    expect(mock.requests.filter((r) => r.startsWith('/api/auth') || r.startsWith('/api/portfolio') || r.startsWith('/api/admin'))).toEqual([])
  })

  for (const hash of ['#/portfolio', '#/admin', '#/login', '#/project/anderes-projekt']) {
    test(`leitet ${hash} auf das lokale Projekt um`, async ({ page }) => {
      await openLocal(page, hash)
      await expect(page).toHaveURL(new RegExp(`#/project/${PILOT_KEY}$`))
      await expect(page.getByRole('tab', { name: 'Board', selected: true })).toBeVisible()
    })
  }

  test('Deep Links auf Tabs und Lauf funktionieren lokal', async ({ page }) => {
    await openLocal(page, `#/project/${PILOT_KEY}?tab=runs`)
    await expect(page.getByRole('tab', { name: 'Läufe', selected: true })).toBeVisible()
    await page.goto(`${mock.url}/#/project/${PILOT_KEY}?tab=attention`)
    await expect(page.getByRole('tab', { name: /Aufmerksamkeit/, selected: true })).toBeVisible()
    await page.goto(`${mock.url}/#/run/${PILOT_KEY}/${PILOT_RUN}`)
    await expect(page.getByRole('heading', { level: 1, name: '088-kartenansicht' })).toBeVisible()
    await expect(page.getByTestId('round-1')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Portfolio' })).toHaveCount(0)
    await page.getByRole('link', { name: PILOT_KEY }).click()
    await expect(page.getByRole('tab', { name: 'Board', selected: true })).toBeVisible()
  })

  test('zeigt teilweise erledigte Tasks (tasks.partial)', async ({ page }) => {
    const variant = structuredClone(board)
    const target = variant.specs.find((s) => !s.descoped && s.tasks.open + s.tasks.done > 0)!
    target.tasks = { ...target.tasks, partial: 2 }
    const other = await startMockBoardServer(variant, events)
    try {
      await page.goto(`${other.url}/`)
      await expect(page.getByTestId(`spec-${target.number}`).getByTestId('tasks-partial')).toHaveText(/2 teilweise/)
    } finally {
      await other.close()
    }
  })
})

test.describe('Vergleich lokal ↔ online (SC-001)', () => {
  test('Projektansicht ist bei gleichen Daten pixelgleich', async ({ browser }) => {
    const localCtx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, locale: 'de-DE', timezoneId: 'Europe/Berlin' })
    const onlineCtx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, locale: 'de-DE', timezoneId: 'Europe/Berlin', baseURL: 'http://127.0.0.1:3100' })
    try {
      await apiLogin(onlineCtx)
      const local = await localCtx.newPage()
      const online = await onlineCtx.newPage()
      await local.clock.setFixedTime(FIXED_NOW)
      await online.clock.setFixedTime(FIXED_NOW)
      await local.goto(`${mock.url}/`)
      await online.goto(`/#/project/${PILOT_KEY}`)
      await expect(local.getByTestId('project-tabs')).toBeVisible()
      await expect(online.getByTestId('project-tabs')).toBeVisible()
      await settle(local)
      await settle(online)

      const clip = { x: 0, y: 0, width: 1920, height: 1700 }
      await local.screenshot({ path: `${SHOTS}local-project-1920.png`, fullPage: true, clip })
      await online.screenshot({ path: `${SHOTS}online-project-1920.png`, fullPage: true, clip })

      // Kopfzeile und Brotkrumen unterscheiden sich bewusst (Lokal, kein Portfolio). Die Projektansicht selbst muss gleich sein.
      expect(await local.getByTestId('project-tabs').innerText()).toBe(await online.getByTestId('project-tabs').innerText())
      // Die Kopfzeile ist sticky und würde in den Element-Screenshot ragen.
      for (const p of [local, online]) await p.addStyleTag({ content: 'header { visibility: hidden !important }' })
      const a = await local.getByTestId('project-tabs').screenshot()
      const b = await online.getByTestId('project-tabs').screenshot()
      expect(a.equals(b), 'Projektansicht lokal und online ist pixelgleich').toBe(true)
    } finally {
      await localCtx.close()
      await onlineCtx.close()
    }
  })
})

for (const scheme of ['light', 'dark'] as const) {
  test.describe(`Tooltips und Ticker-Hover (${scheme})`, () => {
    test.use({ colorScheme: scheme })

    test(`Ticker: Details per Maus und Tastatur, lesbar (${scheme})`, async ({ page }) => {
      await openLocal(page)
      const first = page.getByTestId('ticker-item').first()
      await first.scrollIntoViewIfNeeded()

      // Maus
      await first.hover()
      const tip = page.getByRole('tooltip')
      await expect(tip).toBeVisible()
      await expect(tip).toContainText(board.ticker[0]!.commit!)
      await expect(tip).toContainText(board.ticker[0]!.spec!)
      await expect(tip).toContainText(board.ticker[0]!.text!)
      await expect(tip).toContainText(/\d{2}:\d{2}:\d{2} (MESZ|MEZ|GMT\+\d)/)
      expect(await tooltipContrast(page)).toBeGreaterThanOrEqual(7)
      if (scheme === 'light') await page.screenshot({ path: `${SHOTS}ticker-hover.png` })
      else await page.screenshot({ path: `${SHOTS}ticker-hover-dark.png` })

      // Tastatur
      await page.mouse.move(0, 0)
      await expect(tip).toBeHidden()
      await page.locator('body').click({ position: { x: 5, y: 500 } })
      await tabTo(page, 'ticker-item')
      await expect(page.getByRole('tooltip')).toBeVisible()
      await expect(page.getByRole('tooltip')).toContainText(board.ticker[0]!.commit!)
      await page.keyboard.press('Escape')
      await expect(page.getByRole('tooltip')).toBeHidden()
    })

    test(`Kennzahlen und Spaltenköpfe haben Tooltips (${scheme})`, async ({ page }) => {
      await openLocal(page)
      const ids = ['in_progress', 'waiting', 'blocked', 'done', 'lead']
      for (const id of ids) {
        await page.getByTestId(`kpi-tip-${id}`).hover()
        await expect(page.getByRole('tooltip')).toBeVisible()
        await page.mouse.move(0, 0)
        await expect(page.getByRole('tooltip')).toBeHidden()
      }
      // Tastatur
      await tabTo(page, 'kpi-tip-done')
      const tip = page.getByRole('tooltip')
      await expect(tip).toContainText('Fertig = Station')
      expect(await tooltipContrast(page)).toBeGreaterThanOrEqual(7)
      await page.screenshot({ path: scheme === 'light' ? `${SHOTS}metric-tooltip.png` : `${SHOTS}metric-tooltip-dark.png`, clip: { x: 0, y: 0, width: 1920, height: 500 } })

      // Spaltenköpfe: Mensch-Spalte und jede Station
      await page.mouse.move(0, 0)
      for (const col of ['human', 'tasked', 'implemented', 'deployed', 'verified']) {
        const head = page.getByTestId(`head-tip-${col}`)
        await head.scrollIntoViewIfNeeded()
        await head.hover()
        await expect(page.getByRole('tooltip')).toBeVisible()
        if (col === 'tasked') await expect(page.getByRole('tooltip')).toContainText('Freigabe = Taskliste vorhanden, keine Task erledigt, nie ein Lauf gestartet')
        await page.mouse.move(0, 0)
      }
    })
  })
}
