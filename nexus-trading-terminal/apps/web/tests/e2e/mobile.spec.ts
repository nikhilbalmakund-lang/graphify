import { expect, test } from "@playwright/test";

test("mobile layout uses bottom navigation and a drawer", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Primary" });
  for (const label of ["Home", "Markets", "Signals", "Chart", "AI"]) {
    await expect(nav.getByRole("link", { name: label, exact: true })).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "Market scanner" })).toBeVisible({ timeout: 60_000 });
  await nav.getByRole("link", { name: "Signals", exact: true }).click();
  await expect(page).toHaveURL(/\/signals$/);
  await nav.getByRole("button", { name: "More pages" }).click();
  const drawer = page.getByRole("dialog");
  await drawer.getByRole("link", { name: "Backtesting" }).click();
  await expect(page).toHaveURL(/\/backtesting$/);
});
