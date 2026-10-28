// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { checkSession, config, proxy, resetSessionCache } from "../proxy";

function req(path: string, token?: string) {
  return new NextRequest(`http://127.0.0.1:3000${path}`, token ? { headers: { cookie: `nv_session=${token}` } } : {});
}

// NextRequest test ortamında 127.0.0.1'i localhost'a çeviriyor; canlı davranış curl ile ayrıca doğrulandı
function loc(res: Response): string | null {
  const raw = res.headers.get("location");
  if (!raw) return null;
  const url = new URL(raw);
  return url.pathname + url.search;
}

function backend(status: number) {
  return vi.fn(async () => new Response("{}", { status }));
}

beforeEach(() => resetSessionCache());
afterEach(() => vi.unstubAllGlobals());

describe("proxy (Sprint 94 E5 — kapı hata durumunda kapalı)", () => {
  it("opens the page only when the backend confirms the session", async () => {
    vi.stubGlobal("fetch", backend(200));
    const res = await proxy(req("/bulten", "iyi"));
    expect(res.status).toBe(200);
    expect(res.headers.get("x-middleware-next")).toBe("1");
  });

  it("sends 401 to the login page and drops the cookie", async () => {
    vi.stubGlobal("fetch", backend(401));
    const res = await proxy(req("/kupondas?scope=mine", "uydurma"));
    expect(res.status).toBe(307);
    expect(loc(res)).toBe("/giris?next=%2Fkupondas%3Fscope%3Dmine");
    expect(res.headers.get("set-cookie")).toContain("nv_session=;");
  });

  it.each([
    ["backend error", () => backend(500)],
    ["exception", () => vi.fn(async () => { throw new Error("ECONNREFUSED"); })],
    ["timeout", () => vi.fn(async () => { throw new DOMException("timed out", "TimeoutError"); })],
  ])("shows 503 on %s instead of opening the page", async (_name, make) => {
    vi.stubGlobal("fetch", make());
    const res = await proxy(req("/bulten", "belki"));
    expect(res.status).toBe(503);
    expect(res.headers.get("x-middleware-next")).toBeNull();
    expect(await res.text()).toContain("Hizmet geçici olarak kullanılamıyor");
  });

  it("redirects to login without a cookie and lets the login page through", async () => {
    const fetchSpy = backend(200);
    vi.stubGlobal("fetch", fetchSpy);
    expect((await proxy(req("/bulten"))).status).toBe(307);
    expect((await proxy(req("/giris"))).headers.get("x-middleware-next")).toBe("1");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("skips the login page when already signed in (safe next only)", async () => {
    vi.stubGlobal("fetch", backend(200));
    expect(loc(await proxy(req("/giris", "iyi")))).toBe("/bulten");
    expect(loc(await proxy(req("/giris?next=%2Fkupondas", "iyi")))).toBe("/kupondas");
    expect(loc(await proxy(req("/giris?next=%2F%5Cevil.com", "iyi")))).toBe("/bulten");
  });

  it("caches a confirmed session for 30 s", async () => {
    const fetchSpy = backend(200);
    vi.stubGlobal("fetch", fetchSpy);
    expect(await checkSession("iyi", 1_000)).toBe("ok");
    expect(await checkSession("iyi", 20_000)).toBe("ok");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(await checkSession("iyi", 40_000)).toBe("ok");
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});

describe("proxy matcher", () => {
  const matcher = new RegExp(`^${config.matcher[0]}$`);
  it.each(["/bulten", "/giris", "/girisX", "/apiary", "/wsx", "/", "/favicon.icox", "/analyze/1"])(
    "checks %s", (path) => expect(matcher.test(path)).toBe(true));
  it.each(["/api", "/api/health", "/ws/live-ht", "/_next/static/chunks/a.js", "/_next/image", "/favicon.ico",
    "/robots.txt", "/sitemap.xml"])("skips %s", (path) => expect(matcher.test(path)).toBe(false));
});
