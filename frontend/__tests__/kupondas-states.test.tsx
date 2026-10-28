import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { LocaleProvider } from "@/lib/locale-context";

// Hata ve boş durum ayrı (Sprint 94 L1): yükleme hatası "Henüz kupon yok" gibi görünmemeli
const api = vi.hoisted(() => ({
  getCoupons: vi.fn(),
  getCouponMatches: vi.fn(),
  getMatchOdds: vi.fn(),
  createCoupon: vi.fn(),
}));
vi.mock("@/lib/api", () => api);

import KupondasPage from "@/app/kupondas/page";

afterEach(() => { cleanup(); vi.clearAllMocks(); });

function renderPage() {
  return render(<LocaleProvider initial="tr"><KupondasPage /></LocaleProvider>);
}

it("shows a load error with retry instead of 'no coupons'", async () => {
  api.getCouponMatches.mockResolvedValue([]);
  api.getCoupons.mockRejectedValueOnce(new Error("Sunucuya ulaşılamadı."));
  renderPage();
  expect(await screen.findByText("Sunucuya ulaşılamadı.")).toBeTruthy();
  expect(screen.queryByText("Henüz kupon yok")).toBeNull();
  api.getCoupons.mockResolvedValueOnce({ coupons: [] });
  fireEvent.click(screen.getByRole("button", { name: "Tekrar dene" }));
  expect(await screen.findByText("Henüz kupon yok")).toBeTruthy();
});

it("shows a fixture load error separately from 'no matches'", async () => {
  api.getCoupons.mockResolvedValue({ coupons: [] });
  api.getCouponMatches.mockRejectedValue(new Error("Veri hizmeti geçici olarak kullanılamıyor."));
  renderPage();
  expect(await screen.findByText("Veri hizmeti geçici olarak kullanılamıyor.")).toBeTruthy();
});

it("picks a match from the searchable list; started matches hidden by default (Sprint 94 J10)", async () => {
  const future = new Date(Date.now() + 3 * 3600_000).toISOString();
  const past = new Date(Date.now() - 600_000).toISOString();
  api.getCoupons.mockResolvedValue({ coupons: [] });
  api.getCouponMatches.mockResolvedValue([
    { match_id: "1", home_team: "Betis", away_team: "Sevilla", league_name: "Spanish Copa Del Rey", kickoff_time: future, started: false, analyzed: false },
    { match_id: "2", home_team: "Arsenal", away_team: "Chelsea", league_name: "English Premier League", kickoff_time: future, started: false, analyzed: true },
    { match_id: "3", home_team: "Oynuyor", away_team: "X", league_name: "Peru Liga 1", kickoff_time: past, started: true, analyzed: false },
  ]);
  api.getMatchOdds.mockReturnValue(new Promise(() => {}));
  renderPage();
  expect(await screen.findByText("Betis - Sevilla")).toBeTruthy();
  expect(screen.queryByText("Oynuyor - X")).toBeNull();
  fireEvent.change(screen.getByPlaceholderText("Takım veya lig ara"), { target: { value: "arsenal" } });
  expect(screen.queryByText("Betis - Sevilla")).toBeNull();
  fireEvent.click(screen.getByRole("option", { name: /Arsenal - Chelsea/ }));
  expect(api.getMatchOdds).toHaveBeenCalledWith("2");
  fireEvent.click(screen.getByRole("button", { name: "Başlamışları göster" }));
  fireEvent.change(screen.getByPlaceholderText("Takım veya lig ara"), { target: { value: "" } });
  const started = screen.getByRole("option", { name: /Oynuyor - X/ }) as HTMLButtonElement;
  expect(started.disabled).toBe(true);
});
