import { expect, test } from "@playwright/test";

// Oturumsuz ziyaretçi (Sprint 94 E5/M1): her sayfa giriş sayfasına, dönüş adresiyle
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Giriş zorunluluğu", () => {
  test("oturumsuz sayfa açılışı girişe yönlenir", async ({ page }) => {
    await page.goto("/kupondas");
    await expect(page).toHaveURL(/\/giris\?next=%2Fkupondas/);
    await expect(page.getByRole("button", { name: "Giriş yap" })).toBeVisible();
  });

  test("uydurma çerezle sayfa açılmaz", async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: "nv_session", value: "uydurma", url: baseURL! }]);
    await page.goto("/bulten");
    await expect(page).toHaveURL(/\/giris/);
  });

  test("dış adrese yönlendiren next yok sayılır", async ({ page }) => {
    await page.goto("/giris?next=%2F%5Cevil.com");
    await expect(page.getByRole("button", { name: "Giriş yap" })).toBeVisible();
  });
});
