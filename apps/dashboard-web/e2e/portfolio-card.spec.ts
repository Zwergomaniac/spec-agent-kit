// Spec 009 US5: Portfolio-Karte (ganze Fläche klickbar, Hover, Tastatur) und Layout in voller Breite.
// Screenshots landen in e2e/screenshots/ (nicht eingecheckt).
import { expect, test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { PILOT_KEY, PILOT_RUN } from './fixtures'
import { apiLogin } from './helpers'

const SHOTS = fileURLToPath(new URL('./screenshots/', import.meta.url))
const KEY = 'ai-forge'

async function shot(page: Page, name: string): Promise<void> {
  mkdirSync(SHOTS, { recursive: true })
  await page.screenshot({ path: `${SHOTS}${name}.png`, fullPage: true })
}

async function settle(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(300)
}

test.describe('Portfolio-Karte', () => {
  test.use({ viewport: { width: 1920, height: 1080 } })

  test.beforeEach(async ({ context, page }) => {
    await apiLogin(context)
    await page.goto('/#/portfolio')
    await expect(page.getByTestId(`project-card-${KEY}`)).toBeVisible()
  })

  test('Klick auf die Kartenfläche (nicht nur den Titel) öffnet das Board', async ({ page }) => {
    const card = page.getByTestId(`project-card-${KEY}`)
    // Ecke der Karte: Polsterung ohne eigenen Inhalt.
    await card.click({ position: { x: 8, y: 8 } })
    await expect(page).toHaveURL(new RegExp(`#/project/${KEY}$`))
    await expect(page.getByRole('heading', { level: 1, name: 'AI Forge' })).toBeVisible()
  })

  test('Klick auf Text ohne Link in der Karte öffnet das Board', async ({ page }) => {
    // Der Stretched Link liegt über dem Text: echter Mausklick auf die Textmitte statt Playwright-Aktionsprüfung.
    const box = (await page.getByTestId(`project-card-${KEY}`).getByText(/Letzte Aktivität/).boundingBox())!
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
    await expect(page).toHaveURL(new RegExp(`#/project/${KEY}$`))
  })

  test('Klick auf den Stationsbalken öffnet ebenfalls das Board', async ({ page }) => {
    await page.getByTestId(`project-card-${KEY}`).getByTestId('stage-bar').locator('a[data-stage]').first().click()
    await expect(page).toHaveURL(new RegExp(`#/project/${KEY}$`))
  })

  test('Strg+Klick und Mittelklick öffnen einen neuen Tab', async ({ page, context }) => {
    const card = page.getByTestId(`project-card-${KEY}`)
    for (const click of [{ modifiers: ['Control' as const] }, { button: 'middle' as const }]) {
      const popup = context.waitForEvent('page')
      await card.click({ position: { x: 8, y: 8 }, ...click })
      const tab = await popup
      await tab.waitForLoadState()
      expect(tab.url()).toContain(`#/project/${KEY}`)
      await tab.close()
      // Die Ausgangsseite bleibt auf dem Portfolio.
      await expect(page).toHaveURL(/#\/portfolio$/)
    }
  })

  test('innere Links führen zu ihrem eigenen Ziel', async ({ page }) => {
    const card = page.getByTestId(`project-card-${PILOT_KEY}`)
    await card.getByRole('link', { name: new RegExp(PILOT_RUN) }).click()
    await expect(page).toHaveURL(new RegExp(`#/run/${PILOT_KEY}/${PILOT_RUN}$`))

    await page.goBack()
    await expect(card).toBeVisible()
    await card.getByRole('link', { name: 'Lauf ansehen' }).click()
    await expect(page).toHaveURL(new RegExp(`#/run/${PILOT_KEY}/${PILOT_RUN}$`))
  })

  test('Tastatur: Tab erreicht die Karte, Fokusrahmen sichtbar, Enter öffnet das Board', async ({ page }) => {
    const card = page.getByTestId(`project-card-${KEY}`)
    const link = card.getByRole('link', { name: 'AI Forge' })
    await page.locator('body').click({ position: { x: 5, y: 5 } })
    let reached = false
    for (let i = 0; i < 60 && !reached; i++) {
      await page.keyboard.press('Tab')
      reached = await link.evaluate((el) => el === document.activeElement)
    }
    expect(reached, 'Karte per Tab erreichbar').toBe(true)
    await expect(link).toBeFocused()
    // Sichtbarer Fokusrahmen an der Karte (Ring als box-shadow) und eingeblendeter Hinweis.
    const shadow = await card.evaluate((el) => getComputedStyle(el).boxShadow)
    expect(shadow).not.toBe('none')
    await expect(card.getByTestId('open-hint')).toHaveCSS('opacity', '1')
    await shot(page, 'portfolio-focus')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(new RegExp(`#/project/${KEY}$`))
  })

  test('Hover: Zeiger, hervorgehobener Rahmen und Hinweis „Board öffnen“', async ({ page }) => {
    await settle(page)
    const card = page.getByTestId(`project-card-${KEY}`)
    const hint = card.getByTestId('open-hint')
    await expect(hint).toHaveCSS('opacity', '0')
    const before = await card.evaluate((el) => getComputedStyle(el).borderTopColor)

    await card.hover({ position: { x: 12, y: 40 } })
    await expect(hint).toHaveCSS('opacity', '1')
    await expect(hint).toContainText('Board öffnen')
    await expect.poll(() => card.evaluate((el) => getComputedStyle(el).borderTopColor)).not.toBe(before)
    const cursor = await page.evaluate(() => {
      const el = document.elementFromPoint(window.innerWidth / 2, window.innerHeight / 2)
      return el ? getComputedStyle(el).cursor : ''
    })
    // Über der Karte (Mitte der Karte ist per Hover darunter) gilt der Zeiger der Karte.
    const box = (await card.boundingBox())!
    const pointer = await page.evaluate(
      ([x, y]) => getComputedStyle(document.elementFromPoint(x!, y!)!).cursor,
      [box.x + 12, box.y + 40]
    )
    expect(pointer).toBe('pointer')
    expect(cursor).toBeTruthy()

    await page.waitForTimeout(250) // Übergang abwarten
    mkdirSync(SHOTS, { recursive: true })
    const pad = 24
    await page.screenshot({
      path: `${SHOTS}portfolio-hover.png`,
      clip: { x: Math.max(0, box.x - pad), y: Math.max(0, box.y - pad), width: box.width + 2 * pad, height: box.height + 2 * pad }
    })
  })

  test('Karte zeigt Stationsbalken, fertige Specs, Vorschau und Marker', async ({ page }) => {
    const card = page.getByTestId(`project-card-${PILOT_KEY}`)
    await expect(card.getByTestId('stage-bar').locator('a[data-stage]').first()).toHaveAttribute('title', /Specs?$/)
    await expect(card.getByText('Fertig', { exact: true })).toBeVisible()
    await expect(card.getByTestId('attention-preview').getByRole('listitem')).toHaveCount(3)
    await expect(card.getByTestId('last-marker')).toContainText('Deploy')
  })
})

test.describe('Dark Mode', () => {
  test.use({ viewport: { width: 1920, height: 1080 }, colorScheme: 'dark' })

  test('Hover und Portfolio im dunklen Design', async ({ context, page }) => {
    await apiLogin(context)
    await page.goto('/#/portfolio')
    const card = page.getByTestId(`project-card-${KEY}`)
    await expect(card).toBeVisible()
    await settle(page)
    await shot(page, 'portfolio-1920-dark')
    await card.hover({ position: { x: 12, y: 40 } })
    await page.waitForTimeout(250)
    const box = (await card.boundingBox())!
    await page.screenshot({ path: `${SHOTS}portfolio-hover-dark.png`, clip: { x: box.x - 24, y: box.y - 24, width: box.width + 48, height: box.height + 48 } })
  })
})

// B04b: Die volle Breite wird genutzt, ohne horizontales Scrollen.
for (const width of [1440, 1920, 2560]) {
  test.describe(`Layout bei ${width} px`, () => {
    test.use({ viewport: { width, height: 1080 } })

    test.beforeEach(async ({ context }) => {
      await apiLogin(context)
    })

    async function expectFullWidth(page: Page): Promise<void> {
      const main = await page.locator('main').boundingBox()
      expect(main).toBeTruthy()
      // Seitlicher Innenabstand höchstens 2 x 40 px (lg:px-10); bis 2400 px Obergrenze keine feste schmale Breite.
      expect(main!.width).toBeGreaterThanOrEqual(Math.min(width, 2400) - 1)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow).toBeLessThanOrEqual(0)
      const inner = await page.evaluate(() => {
        const m = document.querySelector('main')!
        const cs = getComputedStyle(m)
        return m.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)
      })
      expect(inner).toBeGreaterThanOrEqual(Math.min(width, 2400) - 2 * 40 - 1)
    }

    test('Portfolio füllt die Zeile mit mehreren Karten', async ({ page }) => {
      await page.goto('/#/portfolio')
      await expect(page.getByTestId(`project-card-${KEY}`)).toBeVisible()
      await settle(page)
      await expectFullWidth(page)

      const xs = await page.getByTestId('portfolio-grid').locator('> *').evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().x)))
      const firstRow = xs.filter((x, i) => i === 0 || x > xs[0]!).length
      const columns = new Set(xs).size
      expect(columns).toBeGreaterThanOrEqual(Math.min(7, Math.floor((Math.min(width, 2400) - 80 + 16) / 356)))
      expect(firstRow).toBeGreaterThanOrEqual(2)

      // Die Karten reichen bis an den rechten Rand des Inhaltsbereichs.
      const right = await page
        .getByTestId('portfolio-grid')
        .locator('> *')
        .evaluateAll((els) => Math.max(...els.map((e) => e.getBoundingClientRect().right)))
      expect(right).toBeGreaterThanOrEqual(Math.min(width, 2400) - 40 - 24)
      await shot(page, `portfolio-${width}`)
    })

    test('Projekt, Lauf und Admin nutzen die volle Breite', async ({ page }) => {
      await page.goto(`/#/project/${PILOT_KEY}`)
      await expect(page.getByRole('heading', { level: 1, name: 'ImmoAgent' })).toBeVisible()
      await settle(page)
      await expectFullWidth(page)
      await shot(page, `project-board-${width}`)

      await page.goto(`/#/run/${PILOT_KEY}/${PILOT_RUN}`)
      await expect(page.getByTestId('round-1')).toBeVisible()
      await settle(page)
      await expectFullWidth(page)
      await shot(page, `run-${width}`)

      await page.goto('/#/admin')
      await expect(page.getByTestId(`admin-row-${PILOT_KEY}`)).toBeVisible()
      await expectFullWidth(page)
      await shot(page, `admin-${width}`)
    })
  })
}
