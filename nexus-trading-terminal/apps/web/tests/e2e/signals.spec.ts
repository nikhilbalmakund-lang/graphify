import { expect, test } from "@playwright/test";

test("run the signal pipeline and read the result", async ({ page }) => {
  await page.goto("/signals");
  await expect(page.getByRole("heading", { name: "AI Signals", level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Analyze now" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Asset").selectOption("EURUSD");
  await dialog.getByRole("button", { name: "Run analysis" }).click();
  await expect(page).toHaveURL(/\/signals\/sig_/, { timeout: 90_000 });

  // The score is a 0-100 quality score, never presented as a win probability.
  await expect(page.getByRole("img", { name: /Signal score \d+ out of 100/ })).toBeVisible();
  await expect(page.getByText(/% chance/i)).toHaveCount(0);
  await expect(page.getByText("DEMO MODE").first()).toBeVisible();

  await page.getByRole("tab", { name: "Factors & score" }).click();
  await expect(page.getByText("Total signal score")).toBeVisible();
  await page.getByRole("tab", { name: "AI review" }).click();
  await expect(page.getByText(/No AI review stored|AI review unavailable/).first()).toBeVisible();
  await page.getByRole("tab", { name: "Versions & outcome" }).click();
  await expect(page.getByText("Signal engine")).toBeVisible();
});

test("scanner ranks instruments without promising outcomes", async ({ page }) => {
  await page.goto("/scanner");
  await expect(page.getByText(/not guaranteed to work/)).toBeVisible({ timeout: 90_000 });
  await expect(page.getByRole("columnheader", { name: /Score/ })).toBeVisible();
});
