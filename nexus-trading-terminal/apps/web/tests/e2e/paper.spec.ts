import { expect, test } from "@playwright/test";

test.beforeAll(async ({ request }) => {
  // Make the flow independent of the synthetic calendar's news blackout windows.
  const res = await request.put("/api/settings/risk", { data: { news_filter: false } });
  expect(res.ok()).toBeTruthy();
});

test("place a SIMULATED order, see the position, use the kill switch", async ({ page, request }) => {
  const [quote] = (await (await request.get("/api/market/quotes?symbols=BTCUSD")).json()) as { ask: number }[];
  await page.goto("/paper-trading");
  await expect(page.getByText("PAPER TRADING · SIMULATED · NO REAL MONEY")).toBeVisible();

  await page.getByLabel("Asset").selectOption("BTCUSD");
  await page.getByLabel("Lots").fill("0.05");
  await page.getByLabel("Stop loss").fill(String(Math.round(quote.ask * 0.99)));
  await page.getByLabel("TP1 price").fill(String(Math.round(quote.ask * 1.02)));
  await page.getByRole("button", { name: /Place SIMULATED market buy/ }).click();
  await expect(page.getByRole("tab", { name: "Open positions (1)" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("cell", { name: "BTCUSD" }).first()).toBeVisible();

  await page.getByRole("button", { name: "Emergency kill switch" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Activate kill switch" }).click();
  await expect(page.getByText("Emergency kill switch is ACTIVE")).toBeVisible();

  // New orders are blocked while the kill switch is active.
  await page.getByRole("button", { name: /Place SIMULATED market buy/ }).click();
  await expect(page.getByText("Order rejected by the risk engine")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Open positions (1)" })).toBeVisible();

  await page.getByRole("button", { name: "Release kill switch" }).click();
  await expect(page.getByText("Emergency kill switch is ACTIVE")).toHaveCount(0);
});

test("journal records the paper trade", async ({ page }) => {
  await page.goto("/journal");
  await expect(page.getByRole("heading", { name: "Trade Journal", level: 1 })).toBeVisible();
  await expect(page.getByRole("cell", { name: /BTCUSD/ }).first()).toBeVisible({ timeout: 30_000 });
});
