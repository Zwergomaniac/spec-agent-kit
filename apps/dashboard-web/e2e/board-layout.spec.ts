// Board-Layout bei großem Projekt (Fix fix-board-overflow): keine überlappenden Karten, volle Breite,
// kein horizontales Scrollen der Seite, Projekt-Kopfzeile sichtbar. Screenshots landen in e2e/screenshots/.
import { expect, test, type Page } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { LARGE_KEY, LARGE_NAME, LARGE_RUN } from './fixtures'
import { apiLogin } from './helpers'

const SHOTS = fileURLToPath(new URL('./screenshots/', import.meta.url))
const TOLERANCE = 1
const CARDS = '[data-testid^="spec-"], [data-testid="attention-item"]'

async function settle(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(300)
}

async function shot(page: Page, name: string): Promise<void> {
  mkdirSync(SHOTS, { recursive: true })
  // Nur der obere Teil: das ganze Board wäre über 10000 px hoch und nicht lesbar.
  const width = page.viewportSize()!.width
  await page.screenshot({ path: `${SHOTS}${name}.png`, fullPage: true, clip: { x: 0, y: 0, width, height: 1700 } })
}

async function expectNoPageOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow, 'Seite darf nicht horizontal scrollen').toBeLessThanOrEqual(0)
}

/** Meldet Karten, deren Box über den Rand ihrer Spalte hinausragt oder deren Inhalt die Karte sprengt. */
async function overflowingCards(page: Page): Promise<string[]> {
  return page.evaluate(
    ([selector, tol]) => {
      const bad: string[] = []
      for (const el of Array.from(document.querySelectorAll<HTMLElement>(selector as string))) {
        const column = el.closest<HTMLElement>('section[data-testid^="column-"]')
        const name = el.dataset.testid ?? 'karte'
        if (!column) {
          bad.push(`${name}: ohne Spalte`)
          continue
        }
        const a = el.getBoundingClientRect()
        const b = column.getBoundingClientRect()
        if (a.left < b.left - (tol as number) || a.right > b.right + (tol as number)) bad.push(`${name}: ${a.left}-${a.right} gegen ${b.left}-${b.right}`)
        if (el.scrollWidth > el.clientWidth + (tol as number)) bad.push(`${name}: Inhalt ${el.scrollWidth} > Karte ${el.clientWidth}`)
      }
      return bad
    },
    [CARDS, TOLERANCE] as const
  )
}

for (const scheme of ['light', 'dark'] as const) {
  for (const width of [1280, 1440, 1920, 2560]) {
    test.describe(`Großes Projekt ${width} px ${scheme}`, () => {
      test.use({ viewport: { width, height: 1080 }, colorScheme: scheme })

      test.beforeEach(async ({ context }) => {
        await apiLogin(context)
      })

      test('Board: keine Karte ragt über ihre Spalte, volle Breite, Kopfzeile sichtbar', async ({ page }) => {
        await page.goto(`/#/project/${LARGE_KEY}`)
        await expect(page.getByRole('heading', { level: 1, name: LARGE_NAME })).toBeVisible()
        await expect(page.getByTestId('board-columns')).toBeVisible()
        await settle(page)

        expect(await page.getByTestId('attention-item').count()).toBe(19)
        expect(await page.locator('[data-testid^="spec-"]').count()).toBeGreaterThanOrEqual(85)

        expect(await overflowingCards(page), 'Karten über dem Spaltenrand').toEqual([])

        // Spalten decken mindestens 98 % der Container-Breite ab.
        const coverage = await page.evaluate(() => {
          const scroller = document.querySelector<HTMLElement>('[data-testid="board-scroller"]')!
          const cols = Array.from(document.querySelectorAll<HTMLElement>('[data-testid="board-columns"] > section'))
          const first = cols[0]!.getBoundingClientRect()
          const last = cols[cols.length - 1]!.getBoundingClientRect()
          return { ratio: (last.right - first.left) / scroller.clientWidth, count: cols.length, scrolls: scroller.scrollWidth - scroller.clientWidth }
        })
        expect(coverage.count).toBe(9)
        expect(coverage.ratio).toBeGreaterThanOrEqual(0.98)
        expect(coverage.scrolls, 'ab 1280 px scrollt das Board nicht').toBeLessThanOrEqual(0)

        await expectNoPageOverflow(page)

        // Kopfzeile des Projekts (Brotkrumen, Titel, Untertitel) liegt vollständig unter dem fixierten Header.
        const header = (await page.locator('header').first().boundingBox())!
        const boxes = {
          crumbs: await page.getByRole('navigation', { name: 'Brotkrumen' }).boundingBox(),
          title: await page.getByRole('heading', { level: 1, name: LARGE_NAME }).boundingBox(),
          meta: await page.getByText(/^Branch main$/).boundingBox()
        }
        for (const [name, box] of Object.entries(boxes)) {
          expect(box, name).toBeTruthy()
          expect(box!.y, `${name} unter dem Header`).toBeGreaterThanOrEqual(header.y + header.height)
        }
        await expect(page.getByText(/^Branch main$/)).toBeInViewport({ ratio: 1 })

        if (width === 1920 && scheme === 'dark') await shot(page, 'board-large-1920-dark')
        if (width === 2560 && scheme === 'dark') await shot(page, 'board-large-2560-dark')
        if (width === 1280 && scheme === 'light') await shot(page, 'board-large-1280')
      })

      test('Aufmerksamkeit, Läufe, Lauf-Ansicht und Portfolio-Karte laufen nicht über', async ({ page }) => {
        await page.goto(`/#/project/${LARGE_KEY}?tab=attention`)
        await expect(page.getByTestId('attention-row')).toHaveCount(19)
        await settle(page)
        await expectNoPageOverflow(page)

        await page.goto(`/#/project/${LARGE_KEY}?tab=runs`)
        await expect(page.getByTestId(`run-row-${LARGE_RUN}`)).toBeVisible()
        await expectNoPageOverflow(page)

        await page.goto(`/#/run/${LARGE_KEY}/${LARGE_RUN}`)
        await expect(page.getByTestId('round-1')).toBeVisible()
        await settle(page)
        await expectNoPageOverflow(page)

        await page.goto('/#/portfolio')
        await expect(page.getByTestId(`project-card-${LARGE_KEY}`)).toBeVisible()
        await settle(page)
        await expectNoPageOverflow(page)
        const bad = await page.evaluate((key) => {
          const card = document.querySelector<HTMLElement>(`[data-testid="project-card-${key}"]`)!
          const box = card.getBoundingClientRect()
          return Array.from(card.querySelectorAll<HTMLElement>('*'))
            .filter((e) => e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().right > box.right + 1)
            .map((e) => e.tagName)
        }, LARGE_KEY)
        expect(bad, 'Inhalt der Portfolio-Karte ragt aus der Karte').toEqual([])
      })
    })
  }
}

test.describe('Großes Projekt unter 1280 px', () => {
  for (const width of [1024, 900]) {
    test(`${width} px: nur das Board scrollt waagerecht, die Seite nicht`, async ({ page, context }) => {
      await page.setViewportSize({ width, height: 900 })
      await apiLogin(context)
      await page.goto(`/#/project/${LARGE_KEY}`)
      await expect(page.getByTestId('board-columns')).toBeVisible()
      await settle(page)
      await expectNoPageOverflow(page)
      const scrolls = await page.getByTestId('board-scroller').evaluate((el) => el.scrollWidth - el.clientWidth)
      expect(scrolls).toBeGreaterThan(0)
      expect(await overflowingCards(page)).toEqual([])
    })
  }
})
