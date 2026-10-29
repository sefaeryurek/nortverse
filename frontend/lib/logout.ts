import { writeStorage } from "./cart";

/**
 * Çıkış: oturumu kapatır, bu tarayıcıdaki sepeti temizler (Sprint 94 E8 — ortak bilgisayarda sonraki kişi önceki
 * seçimleri görmesin) ve giriş sayfasına tam sayfa yüklemeyle gider (istemci önbelleğindeki kullanıcı verisi de
 * silinsin). Masaüstü ve mobil menü aynı fonksiyonu kullanır.
 */
export async function logoutAndLeave(go: (url: string) => void = (url) => window.location.assign(url)): Promise<void> {
  try { await fetch("/api/auth/logout", { method: "POST" }); } catch { /* çerez yine de süresiyle düşer */ }
  writeStorage([]);
  go("/giris");
}
