import { afterEach, expect, it, vi } from "vitest";
import { analyzeMatch, getFixture, getResults } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

it("gives a useful service failure message instead of HTTP details", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("internal trace", { status: 503 })));
  await expect(analyzeMatch("123")).rejects.toMatchObject({ status: 503, message: expect.stringContaining("geçici") });
});

it("escapes query input instead of injecting parameters", async () => {
  const mock = vi.fn().mockResolvedValue(new Response("[]"));
  vi.stubGlobal("fetch", mock);
  await getFixture("2026-01-01&all=true");
  expect(mock.mock.calls[0][0]).toContain("date=2026-01-01%26all%3Dtrue");
});

it("turns malformed server JSON into a readable error", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>proxy error</html>")));
  await expect(analyzeMatch("123")).rejects.toThrow("geçersiz bir yanıt");
});

it("preserves caller cancellation", async () => {
  const controller = new AbortController();
  controller.abort();
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(controller.signal.reason));
  await expect(analyzeMatch("123", controller.signal)).rejects.toBe(controller.signal.reason);
});

const fixtureRow = { match_id: "123", home_team: "Home", away_team: "Away",
  league_code: "ENG PR", league_name: "Premier League", kickoff_time: null };

it.each([null, {}, [null], [{ ...fixtureRow, home_team: 7 }],
  [{ ...fixtureRow, kickoff_time: "not-a-date" }], [fixtureRow, fixtureRow]])(
  "rejects malformed fixture JSON before rendering: %s", async (payload) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(payload))));
    await expect(getFixture("2026-09-14")).rejects.toThrow("geçersiz maç verisi");
  },
);

it("accepts valid fixture records with unknown kickoff", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([fixtureRow]))));
  await expect(getFixture("2026-09-14")).resolves.toEqual([fixtureRow]);
});

it("rejects a finished result without a complete final score", async () => {
  const row = { ...fixtureRow, actual_ft_home: 1, actual_ft_away: null,
    actual_ht_home: null, actual_ht_away: null, status: "finished", result: "1",
    kg_var: null, over_25: null, katman_a_covered: null };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([row]))));
  await expect(getResults("2026-09-14")).rejects.toThrow("geçersiz maç verisi");
});

it("keeps a live score separate from a confirmed final result", async () => {
  const row = { ...fixtureRow, actual_ft_home: null, actual_ft_away: null,
    actual_ht_home: null, actual_ht_away: null, live_home: 2, live_away: 1,
    score_checked_at: "2026-09-19T18:00:00+00:00", status: "live", result: null,
    kg_var: null, over_25: null, katman_a_covered: null };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([row]))));
  await expect(getResults("2026-09-19")).resolves.toEqual([row]);
});

it("preserves cancellation while reading the response body", async () => {
  const controller = new AbortController();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => {
    controller.abort();
    throw controller.signal.reason;
  } }));
  await expect(analyzeMatch("123", controller.signal)).rejects.toMatchObject({ name: "AbortError" });
});
