import { expect, test as setup } from "@playwright/test";

/**
 * Uçtan uca testlerden önce bir kez giriş yapılır, oturum çerezi dosyaya kaydedilir (Sprint 94 M1).
 * Hesap: backend klasöründe `python -m app.cli.main create-user e2e --password <şifre>`; şifre ve ad
 * E2E_USER / E2E_PASSWORD ortam değişkenlerinden okunur (CI iş tanımı bunları kendisi hazırlar).
 */
export const AUTH_FILE = "e2e/.auth/user.json";

setup("giriş yap", async ({ page }) => {
  const user = process.env.E2E_USER;
  const password = process.env.E2E_PASSWORD;
  if (!user || !password) {
    throw new Error("E2E_USER ve E2E_PASSWORD gerekli (create-user e2e --password ... ile açılan hesap)");
  }
  await page.goto("/giris?next=%2Fkupondas");
  await page.getByLabel("Kullanıcı adı").fill(user);
  await page.getByLabel("Şifre").fill(password);
  await page.getByRole("button", { name: "Giriş yap" }).click();
  await expect(page).toHaveURL(/\/kupondas/, { timeout: 15_000 }); // güvenli dönüş adresi korunur
  await page.context().storageState({ path: AUTH_FILE });
});
