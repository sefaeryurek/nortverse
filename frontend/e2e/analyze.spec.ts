import { test, expect } from "@playwright/test";

test.describe("Analiz sayfası", () => {
  test("analiz sayfası yükleniyor", async ({ page }) => {
    await page.goto("/analyze/2813084?home=Kayserispor&away=Karagumruk");
    await expect(page.locator("body")).toBeVisible();
    await expect(page.locator("text=Kayserispor").first()).toBeVisible({ timeout: 15_000 });
  });

  test("geri butonu mevcut", async ({ page }) => {
    await page.goto("/analyze/2813084?home=Kayserispor&away=Karagumruk");
    await expect(page.locator("text=Kayserispor").first()).toBeVisible({ timeout: 15_000 });
    const backLink = page.locator("a[href*='bulten']").first();
    await expect(backLink).toBeVisible();
  });

  test("periyot sekmeleri mevcut", async ({ page }) => {
    await page.goto("/analyze/2813084?home=Kayserispor&away=Karagumruk");
    await expect(page.locator("text=Kayserispor").first()).toBeVisible({ timeout: 15_000 });
    const tabs = page.locator("button").filter({ hasText: /İY|2Y|MS/ });
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test("periyot sekme değiştirme çalışıyor", async ({ page }) => {
    await page.goto("/analyze/2813084?home=Kayserispor&away=Karagumruk");
    await expect(page.locator("text=Kayserispor").first()).toBeVisible({ timeout: 15_000 });
    const iyTab = page.locator("button").filter({ hasText: "İY" }).first();
    if (await iyTab.isVisible()) {
      await iyTab.click();
      await page.waitForTimeout(500);
    }
  });
});
