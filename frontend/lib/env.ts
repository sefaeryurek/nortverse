// Tek kaynaklı env okuma — next.config.ts ve lib/api.ts ikisi de buradan tüketir.

/**
 * lib/api.ts fetch çağrılarında kullanılan base URL.
 *
 * - SSR: BACKEND_URL, sonra NEXT_PUBLIC_API_URL; varsayılan http://127.0.0.1:8000 (backend sadece 127.0.0.1 dinler; localhost bazı sistemlerde ::1 olur).
 * - Browser: NEXT_PUBLIC_API_URL varsa direkt; yoksa aynı origin üzerinden proxy.
 * - Sunucu tarafında fetch mutlak URL gerektirir.
 */
export function getApiBase(): string {
  const publicUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "");
  if (typeof window !== "undefined") return publicUrl || "";
  return (process.env.BACKEND_URL || publicUrl || "http://127.0.0.1:8000").replace(/\/+$/, "");
}

/**
 * next.config.ts rewrite proxy hedefi.
 * Yerelde 127.0.0.1:8000 varsayılanı var (Vercel'de BACKEND_URL set olur).
 */
export function getProxyTarget(): string {
  return (process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
}
