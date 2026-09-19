import { test, expect } from "@playwright/test";

test.describe("Sayfa yüklenme ve navigasyon", () => {
  test("root / bulten'e yönlendirir", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/bulten/);
  });

  test("bülten sayfası başlık ve yapı kontrolü", async ({ page }) => {
    await page.goto("/bulten");
    await expect(page.locator("body")).toBeVisible();
    const dayTabs = page.locator('a[href*="?date="], [aria-current="date"]');
    await expect(dayTabs.first()).toBeVisible({ timeout: 10_000 });
  });

  test("sonuçlar sayfası yükleniyor", async ({ page }) => {
    await page.goto("/sonuclar");
    await expect(page.locator("body")).toBeVisible();
    const dayTabs = page.locator('a[href*="?date="], [aria-current="date"]');
    await expect(dayTabs.first()).toBeVisible({ timeout: 10_000 });
  });

  test("sidebar navigasyon linkleri mevcut (desktop)", async ({ page }) => {
    await page.goto("/bulten");
    const sidebar = page.locator("nav, aside").first();
    await expect(sidebar).toBeVisible({ timeout: 10_000 });
  });

  test("DayTabs 8 gün gösteriyor", async ({ page }) => {
    await page.goto("/bulten");
    const tabs = page.locator('a[href*="?date="], [aria-current="date"]');
    await expect(tabs).toHaveCount(8, { timeout: 10_000 });
  });

  test("DayTabs tarih değiştirme", async ({ page }) => {
    await page.goto("/bulten");
    const dayLink = page.locator('a[href*="?date="]').first();
    await expect(dayLink).toBeVisible({ timeout: 10_000 });
    await dayLink.click();
    await expect(page).toHaveURL(/date=/);
  });
});
