import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getProxyTarget } from "./lib/env";
import { safeNext } from "./lib/safe-next";

/**
 * Giriş zorunluluğu (Sprint 93): oturum çerezi olmayan ya da geçersiz olan ziyaretçi /giris'e yönlendirilir.
 * Oturum backend'de doğrulanır (/api/auth/me); /api ve /ws istekleri bu dosyadan geçmez, backend kendisi
 * kontrol eder.
 *
 * Sprint 94 E5 — kapı hata durumunda kapalı kalır: sayfa yalnızca backend oturumu açıkça onaylarsa (200) açılır.
 * 401 → giriş sayfası; backend kapalı / hata / zaman aşımı → 503 sayfası (eskiden sayfa açılıyordu, çerez değeri
 * uydurma olsa bile). Onaylanan oturum 30 sn bellekte tutulur (her ön yükleme backend'e gitmesin).
 */
const COOKIE = "nv_session";
const SESSION_CACHE_MS = 30_000;
const SESSION_CACHE_MAX = 500;
const CHECK_TIMEOUT_MS = 5_000;
const sessionCache = new Map<string, number>(); // çerez değeri → onayın geçerlilik sonu

export type SessionCheck = "ok" | "invalid" | "unavailable";

export function resetSessionCache(): void {
  sessionCache.clear();
}

export async function checkSession(token: string, now: number = Date.now()): Promise<SessionCheck> {
  const until = sessionCache.get(token);
  if (until !== undefined && until > now) return "ok";
  sessionCache.delete(token);
  try {
    const res = await fetch(`${getProxyTarget()}/api/auth/me`, {
      headers: { cookie: `${COOKIE}=${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(CHECK_TIMEOUT_MS),
    });
    if (res.ok) {
      if (sessionCache.size >= SESSION_CACHE_MAX) sessionCache.clear();
      sessionCache.set(token, now + SESSION_CACHE_MS);
      return "ok";
    }
    return res.status === 401 ? "invalid" : "unavailable";
  } catch {
    return "unavailable";
  }
}

function isLoginPath(pathname: string): boolean {
  return pathname === "/giris" || pathname.startsWith("/giris/");
}

// Yönlendirme adresi isteğin kendi adresinden kurulur: `nextUrl.clone()` 127.0.0.1'i localhost'a çeviriyor,
// 127.0.0.1'e yazılmış çerez localhost'a gitmediği için yerelde giriş döngüsü oluşurdu.
function toLogin(request: NextRequest, clearCookie: boolean): NextResponse {
  const login = new URL("/giris", request.url);
  const next = request.nextUrl.pathname + request.nextUrl.search;
  if (next !== "/") login.searchParams.set("next", next);
  const response = NextResponse.redirect(login);
  if (clearCookie) response.cookies.delete(COOKIE);
  return response;
}

const UNAVAILABLE = {
  tr: { title: "Hizmet geçici olarak kullanılamıyor", body: "Oturum doğrulanamadı. Birazdan yeniden deneyin.", retry: "Yeniden dene" },
  en: { title: "Service temporarily unavailable", body: "Your session could not be verified. Please try again shortly.", retry: "Try again" },
};

function unavailable(request: NextRequest): Response {
  const text = UNAVAILABLE[request.cookies.get("nv_lang")?.value === "en" ? "en" : "tr"];
  const href = request.nextUrl.pathname + request.nextUrl.search;
  const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">`
    + `<title>${text.title}</title></head>`
    + `<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0e14;color:#e6e9ef;font-family:system-ui,sans-serif;padding:16px">`
    + `<main style="max-width:420px;text-align:center"><h1 style="font-size:18px">${text.title}</h1>`
    + `<p style="color:#9aa3b2;font-size:14px">${text.body}</p>`
    + `<a href="${encodeURI(href)}" style="color:#7aa2ff">${text.retry}</a></main></body></html>`;
  return new Response(html, {
    status: 503,
    headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "retry-after": "30" },
  });
}

export async function proxy(request: NextRequest) {
  const token = request.cookies.get(COOKIE)?.value;
  const onLogin = isLoginPath(request.nextUrl.pathname);
  if (!token) return onLogin ? NextResponse.next() : toLogin(request, false);

  const state = await checkSession(token);
  if (state === "ok") {
    if (!onLogin) return NextResponse.next();
    // Girişliyken giriş sayfası açılmaz: istenen sayfaya (ya da bültene) geçilir
    const origin = new URL(request.url).origin;
    return NextResponse.redirect(new URL(safeNext(request.nextUrl.searchParams.get("next"), origin), origin));
  }
  if (state === "invalid") {
    if (!onLogin) return toLogin(request, true);
    const response = NextResponse.next();
    response.cookies.delete(COOKIE);
    return response;
  }
  return onLogin ? NextResponse.next() : unavailable(request);
}

export const config = {
  // Ön ekler yol sınırıyla: "/apiary", "/girisX" gibi yollar da kontrolden geçer (eskiden "api"/"giris" ile
  // başlayan her yol atlanıyordu). /giris de artık burada: girişliyken giriş sayfası atlanır.
  matcher: ["/((?!(?:api|ws)(?:/|$)|_next/static/|_next/image|favicon.ico$|robots.txt$|sitemap.xml$).*)"],
};
