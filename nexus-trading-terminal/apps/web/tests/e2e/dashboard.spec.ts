import { expect, test } from "@playwright/test";

test("dashboard shows a clearly labelled DEMO market overview", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "DEMO MODE" })).toBeVisible();
  for (const sym of ["XAUUSD", "EURUSD", "BTCUSD", "NAS100", "USOIL"]) {
    await expect(page.getByRole("link", { name: new RegExp(`^${sym} .*open chart`) })).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "Risk status" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "AI market briefing" })).toBeVisible();
  // Accessibility basics: skip link and main landmark.
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeAttached();
  await expect(page.getByRole("main")).toBeVisible();
});

test("keyboard shortcuts and the command palette navigate", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
  await page.keyboard.press("m");
  await expect(page).toHaveURL(/\/markets$/);
  await expect(page.getByRole("heading", { name: "Markets", level: 1 })).toBeVisible();
  await page.keyboard.press("/");
  await page.getByPlaceholder(/Type a command or search/).fill("gold");
  await page.getByRole("option", { name: /Go to Gold/ }).click();
  await expect(page).toHaveURL(/\/chart\?symbol=XAUUSD/);
  await expect(page.getByRole("img", { name: /XAUUSD .* candlestick chart/ })).toBeVisible();
});

test("system status reports every integration honestly", async ({ page }) => {
  await page.goto("/status");
  const table = page.getByRole("table").first();
  for (const name of ["Frontend", "Backend", "Database", "Market Data", "Claude", "Gemini", "News", "Economic Calendar", "Paper Broker"]) {
    await expect(table.getByRole("cell", { name: new RegExp(name) }).first()).toBeVisible();
  }
  await expect(table.getByText("NOT CONFIGURED").first()).toBeVisible();
  await expect(page.getByText("LIVE EXECUTION DISABLED")).toBeVisible();
});
