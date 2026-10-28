import { afterEach, beforeEach, expect, it, vi } from "vitest";

// Oturum düşünce (401) tarayıcı giriş sayfasına, dönüş adresiyle gider (Sprint 94 L1)
let assign: ReturnType<typeof vi.fn>;

function setLocation(path: string) {
  const url = new URL(`http://127.0.0.1:3000${path}`);
  vi.stubGlobal("location", { origin: url.origin, pathname: url.pathname, search: url.search, assign });
}

beforeEach(() => {
  vi.resetModules(); // "bir kez yönlendir" bayrağı her testte sıfırdan
  assign = vi.fn();
  setLocation("/kupondas?scope=mine");
});
afterEach(() => vi.unstubAllGlobals());

it("redirects to the login page with the current path on 401", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 401 })));
  const { getCoupons } = await import("@/lib/api");
  await expect(getCoupons("mine")).rejects.toMatchObject({ status: 401 });
  expect(assign).toHaveBeenCalledWith("http://127.0.0.1:3000/giris?next=%2Fkupondas%3Fscope%3Dmine");
});

it("redirects only once for several failing requests", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 401 })));
  const { getCoupons, getLiveHTMatches } = await import("@/lib/api");
  await Promise.allSettled([getCoupons("all"), getCoupons("mine"), getLiveHTMatches()]);
  expect(assign).toHaveBeenCalledTimes(1);
});

it("does not redirect for other errors or on the login page itself", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 503 })));
  const api = await import("@/lib/api");
  await expect(api.getCoupons("all")).rejects.toMatchObject({ status: 503 });
  expect(assign).not.toHaveBeenCalled();
  setLocation("/giris?next=%2Fbulten");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 401 })));
  await expect(api.getCoupons("all")).rejects.toMatchObject({ status: 401 });
  expect(assign).not.toHaveBeenCalled();
});

it("coupon save also redirects on 401", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Giriş gerekli" }), { status: 401 })));
  const { createCoupon } = await import("@/lib/api");
  const res = await createCoupon([{ match_id: "1", period: "ft", market: "result", selection: "1", line: null, seen_odds: 2 }], null);
  expect(res.ok).toBe(false);
  expect(assign).toHaveBeenCalledTimes(1);
});
