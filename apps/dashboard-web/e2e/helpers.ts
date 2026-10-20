import { expect, type BrowserContext, type Page } from '@playwright/test'
import { ADMIN_PASSWORD } from './fixtures'

/** Meldet über die API an; das Cookie landet im Browser-Kontext. */
export async function apiLogin(context: BrowserContext): Promise<void> {
  const res = await context.request.post('/api/auth/login', { data: { password: ADMIN_PASSWORD } })
  expect(res.ok()).toBe(true)
}

/** Meldet über die Oberfläche an. */
export async function uiLogin(page: Page): Promise<void> {
  await page.getByLabel('Passwort').fill(ADMIN_PASSWORD)
  await page.getByRole('button', { name: 'Anmelden' }).click()
}
