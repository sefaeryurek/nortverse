/**
 * Gölgedeki ligler (Sprint 92): ENG Championship, Almanya 2, Portekiz, Belçika, İskoçya.
 * Tahminleri deftere yazılıyor ama ekranda varsayılan olarak gizli; kullanıcı kenar menüden
 * "Gölge ligleri göster" anahtarını açarsa bülten, canlı sayfa ve değerlendirmede "Deneme" etiketiyle görünür.
 * Tercih dil seçimi gibi çerezde (sunucu bileşenleri de okuyabilsin).
 */
export const SHADOW_COOKIE = "nv_shadow";

export function shadowFromCookie(value: string | undefined | null): boolean {
  return value === "1";
}

/** Tarayıcıda çerezden okur (sunucuda her zaman kapalı). */
export function shadowEnabledInBrowser(): boolean {
  if (typeof document === "undefined") return false;
  return /(?:^|;\s*)nv_shadow=1(?:;|$)/.test(document.cookie);
}

export function setShadowEnabled(on: boolean): void {
  document.cookie = `${SHADOW_COOKIE}=${on ? "1" : "0"};path=/;max-age=${60 * 60 * 24 * 365};samesite=lax`;
  window.location.reload();
}
