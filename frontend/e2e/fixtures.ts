import { test as base, expect, type Page } from "@playwright/test"

export type TestUser = { email: string; password: string }

export function newUser(): TestUser {
  const id = crypto.randomUUID()
  return { email: `e2e-${id}@example.com`, password: `pw-${id}` }
}

// Signs up through the UI. Local Supabase skips email confirmation, so the
// user is signed in right away.
export async function signUp(page: Page, user: TestUser = newUser()) {
  await page.goto("/")
  await page.getByLabel("Email").fill(user.email)
  await page.getByLabel("Password").fill(user.password)
  await page.getByRole("button", { name: "Sign up" }).click()
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible()
  return user
}

export async function signIn(page: Page, user: TestUser) {
  await page.goto("/")
  await page.getByLabel("Email").fill(user.email)
  await page.getByLabel("Password").fill(user.password)
  await page.getByRole("button", { name: "Sign in" }).click()
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible()
}

// Tests that take `user` start on "/" signed in as a brand-new user, so
// they never see each other's data and can run in parallel.
export const test = base.extend<{ user: TestUser }>({
  user: async ({ page }, use) => {
    await use(await signUp(page))
  },
})

export { expect }
