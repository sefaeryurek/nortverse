import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getProxyTarget } from "./lib/env";

/**
 * Giriş zorunluluğu (Sprint 93): oturum çerezi olmayan ya da geçersiz olan ziyaretçi /giris'e yönlendirilir.
 * Oturum backend'de doğrulanır (/api/auth/me); /api ve /ws istekleri bu dosyadan geçmez, backend kendisi
 * kontrol eder.
 */
const COOKIE = "nv_session";

export async function proxy(request: NextRequest) {
  const token = request.cookies.get(COOKIE)?.value;
  if (token) {
    try {
      const res = await fetch(`${getProxyTarget()}/api/auth/me`, {
        headers: { cookie: `${COOKIE}=${token}` },
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      });
      if (res.ok) return NextResponse.next();
      if (res.status !== 401) return NextResponse.next(); // backend kapalı/hatalı → sayfa kendi hatasını gösterir
    } catch {
      return NextResponse.next();
    }
  }
  const login = new URL("/giris", request.url);
  const next = request.nextUrl.pathname + request.nextUrl.search;
  if (next !== "/") login.searchParams.set("next", next);
  const response = NextResponse.redirect(login);
  if (token) response.cookies.delete(COOKIE);
  return response;
}

export const config = {
  matcher: ["/((?!api|ws|_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml|giris).*)"],
};
