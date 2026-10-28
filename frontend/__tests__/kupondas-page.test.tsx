import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { hasStarted, OddsPanel, priceFor } from "@/components/CouponOddsPanel";
import type { MatchOdds } from "@/lib/api";
import { LocaleProvider, useLocale } from "@/lib/locale-context";

function Panel({ now }: { now: number }) {
  const { t } = useLocale();
  return <OddsPanel odds={ODDS} kickoff={KICKOFF} now={now} draft={[]} toggle={() => {}} t={t} locale="tr" />;
}

function renderPanel(now: number) {
  return render(<LocaleProvider initial="tr"><Panel now={now} /></LocaleProvider>);
}

const ODDS: MatchOdds = {
  match_id: "1", home_team: "A", away_team: "B", league_name: null,
  // Eski sunucu yanıtı canlı satır taşısa bile ekranda gösterilmez
  live: { minute: "03", score: "0-0" },
  markets: {
    ft: { closed: null, result: { "1": 2.1, X: 3.3, "2": 3.4 } },
    ht: { closed: null, result: { "1": 2.9, X: 2.1, "2": 3.9 } },
  },
};
const KICKOFF = "2026-10-27T17:00:00+00:00";
const KICK_MS = Date.parse(KICKOFF);

describe("Kupondaş oran paneli (sadece maç öncesi)", () => {
  afterEach(() => cleanup());

  it("hasStarted başlama saatine göre karar verir", () => {
    expect(hasStarted(KICKOFF, KICK_MS - 1)).toBe(false);
    expect(hasStarted(KICKOFF, KICK_MS)).toBe(true);
    expect(hasStarted(null, KICK_MS)).toBe(false);
  });

  it("maç öncesi oran butonları görünür", () => {
    renderPanel(KICK_MS - 60_000);
    expect(screen.queryAllByRole("button").length).toBeGreaterThan(0);
  });

  it("60 dk geçmiş maçta İY dahil hiçbir oran butonu ve canlı satır yok", () => {
    renderPanel(KICK_MS + 60 * 60_000);
    expect(screen.queryAllByRole("button")).toHaveLength(0);
    expect(screen.queryByText(/canlı/)).toBeNull();
    expect(screen.getByText(/kupon sadece maç öncesi/)).toBeTruthy();
  });
});

describe("Taslak oran tazeleme (priceFor)", () => {
  const draft = { match_id: "1", home: "A", away: "B", period: "ft" as const, market: "result" as const, selection: "1", line: null, odds: 2.2 };

  it("açık pazarda güncel oranı verir", () => {
    expect(priceFor(ODDS, draft)).toEqual({ odds: 2.1, line: null });
  });

  it("kapanmış periyotta null döner", () => {
    const closed: MatchOdds = { ...ODDS, markets: { ...ODDS.markets, ft: { closed: "Maç başladı" } } };
    expect(priceFor(closed, draft)).toBeNull();
  });

  it("Ü/A çizgisini de döner", () => {
    const withOu: MatchOdds = { ...ODDS, markets: { ...ODDS.markets, ft: { closed: null, ou: { line: 2.75, over: 1.95, under: 1.85 } } } };
    expect(priceFor(withOu, { ...draft, market: "ou", selection: "over", line: 2.5 })).toEqual({ odds: 1.95, line: 2.75 });
  });
});
