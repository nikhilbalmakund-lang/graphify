import { expect, test } from "@playwright/test";

test("API keys are write-only: never echoed back after saving", async ({ page, request }) => {
  const secret = "e2e-not-a-real-key-9876";
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
  await page.getByLabel("New value for NEWS_API_KEY").fill(secret);
  await page.getByRole("button", { name: "Save NEWS_API_KEY" }).click();
  await expect(page.getByText("Configured ****9876")).toBeVisible();
  await expect(page.getByLabel("New value for NEWS_API_KEY")).toHaveValue("");
  expect(await page.content()).not.toContain(secret);
  const body = JSON.stringify(await (await request.get("/api/settings")).json());
  expect(body).not.toContain(secret);
  await page.getByRole("button", { name: "Clear NEWS_API_KEY" }).click();
  await expect(page.getByText("Configured ****9876")).toHaveCount(0);
});

test("live trading cannot be armed from the UI alone", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Broker & live trading" }).click();
  await expect(page.getByText("Live execution is disabled by default")).toBeVisible();
  await expect(page.getByText("DISABLED", { exact: true })).toBeVisible();
});
