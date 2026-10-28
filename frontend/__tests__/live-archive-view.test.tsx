import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { HighlightList } from "@/components/LiveArchiveView";
import type { LiveArchiveView } from "@/lib/api";
import { LocaleProvider } from "@/lib/locale-context";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  return <LocaleProvider initial="tr">{children}</LocaleProvider>;
}

function view(overrides: Partial<LiveArchiveView> = {}): LiveArchiveView {
  return {
    rule_version: "live-arch-v2",
    ht: { home: 1, away: 0 },
    threshold_pct: 85,
    risky_below_n: 5,
    sources: [],
    highlights: [],
    ...overrides,
  };
}

describe("HighlightList (live-arch-v2)", () => {
  afterEach(cleanup);

  it("pazar başına tek karar: ana oran lig geçmişi, arşivler yan bilgi", () => {
    render(
      <HighlightList
        view={view({
          highlights: [{
            period: "ft", market: "dc", selection: "1X", pct: 93.9, archive: "genel", label: "Genel", n: 12,
            risky: false, sources: ["A1", "Genel"], archive_pct: 100, cond_n: 40, cond_level: "league", conflict: false,
          }],
        })}
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getByText("%93.9")).toBeTruthy();
    expect(screen.getByText("lig geçmişi · 40 maç")).toBeTruthy();
    expect(screen.getByText("A1 + Genel")).toBeTruthy();
    expect(screen.getByText("%100")).toBeTruthy();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });

  it("karar yoksa açıklayıcı mesaj gösterir", () => {
    render(<HighlightList view={view()} />, { wrapper: Wrapper });
    expect(screen.getByText("Bu maçta kurala uyan karar yok")).toBeTruthy();
  });

  it("çelişkide uyarı gösterir", () => {
    render(
      <HighlightList
        view={view({
          highlights: [{
            period: "ft", market: "ou_25", selection: "under", pct: 88, archive: "a3", label: "A3", n: 20,
            risky: false, sources: ["A3"], archive_pct: 90, cond_n: 50, cond_level: "global", conflict: true,
          }],
        })}
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getByText("tüm ligler · 50 maç")).toBeTruthy();
    expect(screen.getByText(/çelişki/)).toBeTruthy();
  });

  it("eski v1 kayıtlı maçta arşiv başına işaretleri gruplar", () => {
    render(
      <HighlightList
        view={view({
          rule_version: "live-arch-v1",
          highlights: [
            { period: "ft", market: "dc", selection: "1X", pct: 100, archive: "a1", label: "A1", n: 3, risky: true },
            { period: "ft", market: "dc", selection: "1X", pct: 95, archive: "genel", label: "Genel", n: 9, risky: false },
          ],
        })}
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
  });
});

describe("PoissonDecisionList (Sprint 94 H3)", () => {
  it("İY skorundan belli kararı gri, model katkısını ayrı etiketler", async () => {
    const { PoissonDecisionList } = await import("@/components/LiveArchiveView");
    const base = { period: "ft", market: "ou_15", pct: 96, cond_n: 300, best: false, rule_version: "live-poisson-v1.1", confirmed: false, historical: null };
    render(
      <LocaleProvider initial="tr">
        <PoissonDecisionList decisions={[
          { ...base, selection: "over", cond_pct: 94, valuable: false },
          { ...base, market: "result", selection: "1", cond_pct: 72, valuable: true },
        ]} />
      </LocaleProvider>,
    );
    expect(screen.getByText("İY skoru zaten söylüyor")).toBeTruthy();
    expect(screen.getByText("model katkısı")).toBeTruthy();
  });
});
