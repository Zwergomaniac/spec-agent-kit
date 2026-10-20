import { expect, test, type Page } from '@playwright/test'
import { PILOT_KEY, PILOT_RUN } from './fixtures'
import { apiLogin, uiLogin } from './helpers'

interface Case {
  name: string
  hash: string
  /** Prüft, dass die richtige Ansicht offen ist. */
  assert: (page: Page) => Promise<void>
}

const activeTab = (name: string | RegExp) => async (page: Page) => {
  await expect(page.getByRole('tab', { name, selected: true })).toBeVisible()
}

const CASES: Case[] = [
  { name: 'Portfolio', hash: '#/portfolio', assert: async (p) => expect(p.getByRole('heading', { level: 1, name: 'Portfolio' })).toBeVisible() },
  { name: 'Projekt (ohne Tab)', hash: `#/project/${PILOT_KEY}`, assert: activeTab('Board') },
  { name: 'Projekt, Tab board', hash: `#/project/${PILOT_KEY}?tab=board`, assert: activeTab('Board') },
  { name: 'Projekt, Tab runs', hash: `#/project/${PILOT_KEY}?tab=runs`, assert: activeTab('Läufe') },
  { name: 'Projekt, Tab attention', hash: `#/project/${PILOT_KEY}?tab=attention`, assert: activeTab(/Aufmerksamkeit/) },
  { name: 'Projekt, Tab conflicts', hash: `#/project/${PILOT_KEY}?tab=conflicts`, assert: activeTab('Konflikte') },
  { name: 'Projekt, unbekannter Tab', hash: `#/project/${PILOT_KEY}?tab=foo`, assert: activeTab('Board') },
  {
    name: 'Lauf',
    hash: `#/run/${PILOT_KEY}/${PILOT_RUN}`,
    assert: async (p) => {
      await expect(p.getByRole('heading', { level: 1, name: '088-kartenansicht' })).toBeVisible()
      await expect(p.getByTestId('round-1')).toBeVisible()
    }
  },
  { name: 'Admin', hash: '#/admin', assert: async (p) => expect(p.getByRole('heading', { level: 1, name: 'Admin' })).toBeVisible() }
]

test.describe('Deep Links nach Login (SC-001)', () => {
  for (const c of CASES) {
    test(`${c.name}: frischer Tab, Login, direkt am Ziel (${c.hash})`, async ({ page }) => {
      await page.goto(`/${c.hash}`)
      await expect(page.getByRole('heading', { name: 'Anmelden' })).toBeVisible()
      // Die URL bleibt beim Ziel, das ist der Rücksprung.
      expect(new URL(page.url()).hash).toBe(c.hash)

      await uiLogin(page)
      await expect(page.getByLabel('Passwort')).toBeHidden()
      expect(new URL(page.url()).hash).toBe(c.hash)
      await c.assert(page)
    })

    test(`${c.name}: bereits angemeldet, neuer Tab (${c.hash})`, async ({ context }) => {
      await apiLogin(context)
      const page = await context.newPage()
      await page.goto(`/${c.hash}`)
      await c.assert(page)
    })
  }
})

test.describe('Anmeldung und Start', () => {
  test('Startansicht ist Portfolio, auch ohne Hash', async ({ context }) => {
    await apiLogin(context)
    const page = await context.newPage()
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1, name: 'Portfolio' })).toBeVisible()
  })

  test('explizites Rücksprungziel #/login?next=… führt nach dem Login zum Ziel', async ({ page }) => {
    await page.goto(`/#/login?next=${encodeURIComponent(`#/project/${PILOT_KEY}?tab=runs`)}`)
    await uiLogin(page)
    await expect(page.getByRole('tab', { name: 'Läufe', selected: true })).toBeVisible()
    expect(new URL(page.url()).hash).toBe(`#/project/${PILOT_KEY}?tab=runs`)
  })

  test('falsches Passwort zeigt einen Fehler und bleibt auf der Anmeldung', async ({ page }) => {
    await page.goto('/#/portfolio')
    await page.getByLabel('Passwort').fill('falsch-falsch-falsch')
    await page.getByRole('button', { name: 'Anmelden' }).click()
    await expect(page.getByText('Das Passwort ist nicht korrekt.')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Anmelden' })).toBeVisible()
  })

  test('Tab-Wechsel aktualisiert die URL (?tab=) und lässt sich mit Zurück rückgängig machen', async ({ context }) => {
    await apiLogin(context)
    const page = await context.newPage()
    await page.goto(`/#/project/${PILOT_KEY}`)
    await page.getByRole('tab', { name: 'Läufe' }).click()
    expect(new URL(page.url()).hash).toBe(`#/project/${PILOT_KEY}?tab=runs`)
    await page.goBack()
    await expect(page.getByRole('tab', { name: 'Board', selected: true })).toBeVisible()
  })

  test('API ohne Session liefert 401', async ({ request }) => {
    const res = await request.get('/api/portfolio')
    expect(res.status()).toBe(401)
  })

  test('Abmelden führt zurück zur Anmeldung', async ({ context }) => {
    await apiLogin(context)
    const page = await context.newPage()
    await page.goto('/#/portfolio')
    await page.getByRole('button', { name: 'Abmelden' }).click()
    await expect(page.getByRole('heading', { name: 'Anmelden' })).toBeVisible()
  })
})
