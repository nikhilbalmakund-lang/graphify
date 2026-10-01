import { expect, test } from "@playwright/test";

test("run a backtest and review equity, drawdown, losing periods and trades", async ({ page }) => {
  await page.goto("/backtesting");
  await expect(page.getByRole("heading", { name: "Backtesting", level: 1 })).toBeVisible();
  const start = new Date(Date.now() - 75 * 86_400_000).toISOString().slice(0, 10);
  await page.getByLabel("Start date").fill(start);
  await page.getByRole("button", { name: "Run Backtest" }).click();
  await expect(page.getByRole("heading", { name: "Equity curve" })).toBeVisible({ timeout: 120_000 });
  await expect(page.getByRole("heading", { name: "Drawdown" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Losing periods" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Trade list/ })).toBeVisible();
  await expect(page.getByText(/DEMO DATA: results are computed on synthetic prices/)).toBeVisible();
});
