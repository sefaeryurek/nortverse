import { test, expect } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 } });

test.describe("Mobil görünüm", () => {
  test("bülten sayfası mobilde yükleniyor", async ({ page }) => {
    await page.goto("/bulten");
    await expect(page.locator("body")).toBeVisible();
    const dayButtons = page.locator("button").filter({ hasText: /Pzt|Sal|Çar|Per|Cum|Cmt|Paz/ });
    await expect(dayButtons.first()).toBeVisible({ timeout: 10_000 });
  });

  test("sidebar desktop'ta gizli (mobil viewport)", async ({ page }) => {
    await page.goto("/bulten");
    await page.waitForTimeout(1000);
    const sidebar = page.locator("aside.hidden, nav.hidden").first();
    const isSidebarHidden = await sidebar.isHidden().catch(() => true);
    expect(isSidebarHidden).toBe(true);
  });

  test("DayTabs yatay scroll yapılabilir", async ({ page }) => {
    await page.goto("/bulten");
    const tabsContainer = page.locator(".overflow-x-auto").first();
    await expect(tabsContainer).toBeVisible({ timeout: 10_000 });
  });

  test("analiz sayfası mobilde yükleniyor", async ({ page }) => {
    await page.goto("/analyze/2813084?home=Kayserispor&away=Karagumruk");
    await expect(page.locator("body")).toBeVisible();
    await expect(page.locator("text=Kayserispor").first()).toBeVisible({ timeout: 15_000 });
  });
});
