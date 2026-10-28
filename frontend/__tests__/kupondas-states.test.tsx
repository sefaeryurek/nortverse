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
