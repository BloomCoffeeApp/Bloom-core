import fs from 'node:fs'
import path from 'node:path'

import type { Page } from '@playwright/test'

import { expect, test } from './fixtures'
import { authHeaders } from './helpers'

const uid = () => Date.now().toString(36).slice(-5)

/** Optional review screenshots: BLOOM_SHOTS=<folder> npm run e2e. */
async function shot(page: Page, name: string) {
  const dir = process.env.BLOOM_SHOTS
  if (!dir) return
  fs.mkdirSync(dir, { recursive: true })
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: true })
}

test('the app manifest and its icons are served', async ({ request }) => {
  const res = await request.get('/manifest.webmanifest')
  expect(res.ok()).toBeTruthy()
  const m = await res.json()
  expect(m.display).toBe('standalone')
  expect(m.start_url).toBe('/')
  expect(m.icons.some((i: { purpose: string }) => i.purpose === 'maskable')).toBeTruthy()
  for (const icon of m.icons as { src: string }[]) expect((await request.get(icon.src)).ok(), icon.src).toBeTruthy()
})

test('a custom role sees only what it is allowed to', async ({ page, browser, request }) => {
  const name = `Mozo ${uid()}`
  await page.goto('/config?tab=roles')
  await expect(page.getByRole('option', { name: /Administrador/ })).toBeVisible()
  await page.getByRole('button', { name: 'Nuevo rol' }).click()
  await page.getByLabel('Nombre del rol').fill(name)
  await page.getByRole('checkbox', { name: 'Avisos y checklists' }).check()
  await expect(page.getByRole('checkbox', { name: 'Vender en el POS' })).toBeChecked()
  await page.getByTestId('role-save').click()
  await expect(page.getByRole('option', { name: new RegExp(name) })).toBeVisible()
  await shot(page, 'roles-editor')

  const headers = await authHeaders(page)
  const roles: { key: string; name: string }[] = await (await request.get('/api/roles', { headers })).json()
  const role = roles.find((r) => r.name === name)!
  const userName = `Juan ${uid()}`
  const created = await request.post('/api/users', { headers, data: { name: userName, pin: '5678', role: role.key, color: 'sky' } })
  expect(created.ok(), await created.text()).toBeTruthy()

  const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } })
  const p = await ctx.newPage()
  await p.goto('/')
  await p.getByRole('button', { name: new RegExp(userName) }).click()
  for (const d of '5678') await p.getByRole('button', { name: d, exact: true }).click()
  await p.getByRole('button', { name: 'Entrar' }).click()
  const nav = p.locator('[data-sidebar="sidebar"]')
  await expect(nav.getByRole('link', { name: 'Punto de venta' })).toBeVisible()
  await expect(nav.getByRole('link', { name: 'Avisos y alertas' })).toBeVisible()
  await expect(nav.getByRole('link', { name: 'Productos' })).toHaveCount(0)
  await expect(nav.getByRole('link', { name: 'Caja' })).toHaveCount(0)
  await expect(nav.getByText(name)).toBeVisible() // role name under the user
  await p.goto('/productos')
  await expect(p.getByText('Sin acceso')).toBeVisible()
  await shot(p, 'roles-restricted-user')
  await ctx.close()
})
