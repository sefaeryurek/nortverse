/** Girişten sonraki dönüş adresi (Sprint 94 E4). */

export const DEFAULT_NEXT = "/bulten";

// Kontrol karakterleri (sekme, satır sonu…) ve ters bölü: tarayıcılar "/\evil.com" ve "/<TAB>/evil.com"
// adreslerini "//evil.com" gibi başka siteye giden adres olarak yorumlar.
const UNSAFE_CHARS = /[\u0000-\u001F\u007F\\]/;

/**
 * Sadece aynı siteye ait yol döner; şüpheli her değerde varsayılan sayfa. Son kontrol tarayıcının kendi
 * çözümlemesiyle yapılır: çözülen adresin kökeni sitenin kökeniyle aynı olmalı.
 */
export function safeNext(raw: string | null | undefined, origin: string): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || UNSAFE_CHARS.test(raw)) return DEFAULT_NEXT;
  let url: URL;
  try {
    url = new URL(raw, origin);
  } catch {
    return DEFAULT_NEXT;
  }
  if (url.origin !== new URL(origin).origin) return DEFAULT_NEXT;
  if (url.pathname === "/giris" || url.pathname.startsWith("/giris/")) return DEFAULT_NEXT;  // döngü olmasın
  return url.pathname + url.search + url.hash;
}
