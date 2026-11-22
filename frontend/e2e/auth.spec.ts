import { expect, newUser, signIn, signUp, test } from "./fixtures"

test("backend and database are reachable", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByLabel("Backend status: ok")).toBeVisible()
})

test("sign up, sign out, sign in again", async ({ page }) => {
  const user = await signUp(page)
  await expect(page.getByText(user.email)).toBeVisible()

  await page.getByRole("button", { name: "Sign out" }).click()
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible()

  await signIn(page, user)
  await expect(page.getByText(user.email)).toBeVisible()
})

test("session survives a reload", async ({ page, user }) => {
  await page.reload()
  await expect(page.getByText(user.email)).toBeVisible()
})

test("wrong password shows an error", async ({ page }) => {
  const user = await signUp(page)
  await page.getByRole("button", { name: "Sign out" }).click()

  await page.getByLabel("Email").fill(user.email)
  await page.getByLabel("Password").fill("wrong-password")
  await page.getByRole("button", { name: "Sign in" }).click()
  await expect(page.getByText("Invalid login credentials")).toBeVisible()
})

test("unknown user can't sign in", async ({ page }) => {
  const { email, password } = newUser()
  await page.goto("/")
  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password").fill(password)
  await page.getByRole("button", { name: "Sign in" }).click()
  await expect(page.getByText("Invalid login credentials")).toBeVisible()
})
