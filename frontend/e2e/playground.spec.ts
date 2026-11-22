import { expect, signUp, test } from "./fixtures"

// playwright.config.ts starts the backend without LLM keys, so these tests
// cover the "no key yet" path. The provider wiring itself is unit-tested in
// backend/tests/test_ai.py with a fake LLM.

test("header says no LLM key is configured", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByLabel("LLM: none")).toHaveText("no LLM key")
})

test("sending a message without a key explains what to do", async ({
  page,
}) => {
  await signUp(page)
  await page.getByLabel("Message").fill("hello")
  await page.getByRole("button", { name: "Send" }).click()
  await expect(page.getByText("No LLM configured")).toBeVisible()
})
