import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import DetailedStats from "@/components/DetailedStats";
import { makePatternResult } from "./fixtures";

afterEach(cleanup);

beforeEach(() => {
  try { localStorage.removeItem("nortverse_detailed_open"); } catch {}
});

describe("DetailedStats", () => {
  it("renders accordion button", () => {
    render(<DetailedStats patternB={null} patternC={null} period="ft" />);
    expect(screen.getByText("Detaylı Analiz")).toBeTruthy();
  });

  it("starts closed by default (no localStorage)", () => {
    render(<DetailedStats patternB={null} patternC={null} period="ft" />);
    const btn = screen.getByRole("button");
    expect(btn.getAttribute("aria-expanded")).toBe("false");
  });

  it("opens on click", () => {
    render(<DetailedStats patternB={null} patternC={null} period="ft" />);
    const btn = screen.getByRole("button");
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-expanded")).toBe("true");
  });

  it("shows empty state for null patterns when open", () => {
    render(<DetailedStats patternB={null} patternC={null} patternD={null} period="ft" />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Arşiv 1: Yeterli veri yok")).toBeTruthy();
    expect(screen.getByText("Arşiv 2: Yeterli veri yok")).toBeTruthy();
    expect(screen.getByText("Arşiv 3: Yeterli veri yok")).toBeTruthy();
  });

  it("renders archive card titles when patterns provided", () => {
    const pattern = makePatternResult({ match_count: 30, result_1_pct: 50 });
    render(<DetailedStats patternB={pattern} patternC={null} period="ft" />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Arşiv 1 — Skor Seti")).toBeTruthy();
    expect(screen.getByText("Arşiv 2: Yeterli veri yok")).toBeTruthy();
  });

  it("shows match count badge", () => {
    const pattern = makePatternResult({ match_count: 42 });
    render(<DetailedStats patternB={pattern} patternC={null} period="ft" />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("42 maç")).toBeTruthy();
  });

  it("renders all three archive cards", () => {
    const b = makePatternResult({ match_count: 30 });
    const c = makePatternResult({ match_count: 25 });
    const d = makePatternResult({ match_count: 20 });
    render(<DetailedStats patternB={b} patternC={c} patternD={d} period="ft" />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Arşiv 1 — Skor Seti")).toBeTruthy();
    expect(screen.getByText("Arşiv 2 — Oran Benzerliği")).toBeTruthy();
    expect(screen.getByText("Arşiv 3 — Cosine Similarity")).toBeTruthy();
  });

  it("hides IY/MS section in ht period", () => {
    const pattern = makePatternResult({
      match_count: 30,
      iy_ms_11_pct: 25, iy_ms_1x_pct: 10, iy_ms_12_pct: 5,
      iy_ms_x1_pct: 10, iy_ms_xx_pct: 15, iy_ms_x2_pct: 5,
      iy_ms_21_pct: 5, iy_ms_2x_pct: 10, iy_ms_22_pct: 15,
    });
    render(<DetailedStats patternB={pattern} patternC={null} period="ht" />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.queryByText("İlk Yarı / Maç Sonucu")).toBeNull();
  });

  it("shows IY/MS section in ft period when data exists", () => {
    const pattern = makePatternResult({
      match_count: 30,
      iy_ms_11_pct: 25, iy_ms_1x_pct: 10, iy_ms_12_pct: 5,
      iy_ms_x1_pct: 10, iy_ms_xx_pct: 15, iy_ms_x2_pct: 5,
      iy_ms_21_pct: 5, iy_ms_2x_pct: 10, iy_ms_22_pct: 15,
    });
    render(<DetailedStats patternB={pattern} patternC={null} period="ft" />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("İlk Yarı / Maç Sonucu")).toBeTruthy();
  });

  it("persists open state to localStorage", () => {
    render(<DetailedStats patternB={null} patternC={null} period="ft" />);
    fireEvent.click(screen.getByRole("button"));
    expect(localStorage.getItem("nortverse_detailed_open")).toBe("1");
  });

  it("toggles back to closed", () => {
    render(<DetailedStats patternB={null} patternC={null} period="ft" />);
    const btn = screen.getByRole("button");
    fireEvent.click(btn);
    fireEvent.click(btn);
    expect(btn.getAttribute("aria-expanded")).toBe("false");
    expect(localStorage.getItem("nortverse_detailed_open")).toBe("0");
  });

  it("shows tüm pazarlar badge", () => {
    render(<DetailedStats patternB={null} patternC={null} period="ft" />);
    expect(screen.getByText("tüm pazarlar (~130 oran)")).toBeTruthy();
  });

  it("renders score frequency when available", () => {
    const pattern = makePatternResult({
      match_count: 30,
      score_freq: { "1-0": 8, "2-1": 5, "0-0": 3 },
    });
    render(<DetailedStats patternB={pattern} patternC={null} period="ft" />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("1-0")).toBeTruthy();
    expect(screen.getByText("Skor Sıklığı")).toBeTruthy();
  });
});
