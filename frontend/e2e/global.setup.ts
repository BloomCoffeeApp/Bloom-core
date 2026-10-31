import fs from 'node:fs'
import path from 'node:path'

import { expect, test as setup } from '@playwright/test'

import { ADMIN, ADMIN_STATE } from './constants'
import { e2eProLicense } from './license'

interface LoginOut {
  token: string
  user: { id: number; name: string }
}

/** First-time setup with demo data (via the API) and a saved, logged-in admin session. */
setup('first-time setup and admin session', async ({ page, request }) => {
  setup.setTimeout(180_000) // seeding demo sales takes a while

  const status = await (await request.get('/api/setup/status')).json()
  let login: LoginOut
  if (status.needs_setup) {
    const res = await request.post('/api/setup', {
      data: { business_name: 'Café de Prueba', admin_name: ADMIN.name, admin_pin: ADMIN.pin, load_demo: true },
      timeout: 170_000,
    })
    expect(res.ok(), await res.text()).toBeTruthy()
    login = await res.json()
  } else {
    const users: { id: number; name: string }[] = await (await request.get('/api/auth/users')).json()
    const admin = users.find((u) => u.name === ADMIN.name)!
    const res = await request.post('/api/auth/login', { data: { user_id: admin.id, pin: ADMIN.pin } })
    expect(res.ok(), await res.text()).toBeTruthy()
    login = await res.json()
  }

  // The suite covers the Pro edition.
  const lic = await request.post('/api/license/import', {
    data: { token: e2eProLicense() },
    headers: { Authorization: `Bearer ${login.token}` },
  })
  expect(lic.ok(), await lic.text()).toBeTruthy()

  await page.goto('/menu') // any page of the origin, to write localStorage
  await page.evaluate(({ token, userId }) => {
    localStorage.setItem('cafe.token', token)
    // The guided tour auto-opens on a user's first login; keep it out of the other specs.
    localStorage.setItem(`bloom.tour.done.${userId}`, '1')
  }, { token: login.token, userId: login.user.id })
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText(ADMIN.name)

  fs.mkdirSync(path.dirname(ADMIN_STATE), { recursive: true })
  await page.context().storageState({ path: ADMIN_STATE })
})
