// Tek kaynaklı env okuma — next.config.ts ve lib/api.ts ikisi de buradan tüketir.
// Davranış değişmez; iki yerde duplicate olan fallback mantığı tek modülde toplanır.

/**
 * lib/api.ts fetch çağrılarında kullanılan base URL.
 *
 * - Vercel SSR (server component): NEXT_PUBLIC_API_URL veya BACKEND_URL set → Railway'e direkt.
 * - Vercel CSR (browser): NEXT_PUBLIC_ ile başlayanlar bundle'a girer; BACKEND_URL görmez → "" döner → Next.js proxy üzerinden Railway'e.
 * - Lokal dev: hiçbir env yok → "" → next.config.ts proxy localhost:8000'a yönlendirir.
 */
export function getApiBase(): string {
  return (
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.BACKEND_URL ||
    ""
  );
}

/**
 * next.config.ts rewrite proxy hedefi.
 * Lokal dev'de localhost:8000 fallback'i var (Vercel'de BACKEND_URL set olur).
 */
export function getProxyTarget(): string {
  return process.env.BACKEND_URL || "http://localhost:8000";
}
