import { expect, it, describe, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import TrendsPanel from "@/components/TrendsPanel";
import type { TrendBlock, TrendsData } from "@/lib/types";

afterEach(() => { cleanup(); });

function makeTrendBlock(overrides: Partial<TrendBlock> = {}): TrendBlock {
  return {
    label: "test",
    sample_size: 10,
    win_pct: 60,
    draw_pct: 20,
    loss_pct: 20,
    kg_var_pct: 50,
    over_25_pct: 55,
    avg_goals_for: 1.5,
    avg_goals_against: 0.8,
    last_n_results: ["G", "B", "M", "G", "G"],
    ...overrides,
  };
}

describe("TrendsPanel", () => {
  it("returns null when trends is null", () => {
    const { container } = render(
      <TrendsPanel trends={null} homeTeam="Kayserispor" awayTeam="Karagumruk" />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("returns null when all trend blocks are null", () => {
    const trends: TrendsData = { home_form: null, away_form: null, h2h: null };
    const { container } = render(
      <TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders section title", () => {
    const trends: TrendsData = {
      home_form: makeTrendBlock(),
      away_form: null,
      h2h: null,
    };
    render(<TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />);
    expect(screen.getByText("Form & H2H Trendleri")).toBeDefined();
  });

  it("renders home form card with team name", () => {
    const trends: TrendsData = {
      home_form: makeTrendBlock(),
      away_form: null,
      h2h: null,
    };
    render(<TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />);
    expect(screen.getAllByText("Ev Form").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Kayserispor").length).toBeGreaterThan(0);
  });

  it("renders away form card with team name", () => {
    const trends: TrendsData = {
      home_form: null,
      away_form: makeTrendBlock(),
      h2h: null,
    };
    render(<TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />);
    expect(screen.getByText("Dep Form")).toBeDefined();
    expect(screen.getByText("Karagumruk")).toBeDefined();
  });

  it("renders h2h card", () => {
    const trends: TrendsData = {
      home_form: null,
      away_form: null,
      h2h: makeTrendBlock(),
    };
    render(<TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />);
    expect(screen.getByText("H2H")).toBeDefined();
    expect(screen.getByText("Ev sahibi perspektifi")).toBeDefined();
  });

  it("renders all three cards when all data present", () => {
    const trends: TrendsData = {
      home_form: makeTrendBlock(),
      away_form: makeTrendBlock(),
      h2h: makeTrendBlock(),
    };
    render(<TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />);
    expect(screen.getAllByText("Ev Form").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Dep Form").length).toBeGreaterThan(0);
    expect(screen.getAllByText("H2H").length).toBeGreaterThan(0);
  });

  it("shows sample size badge", () => {
    const trends: TrendsData = {
      home_form: makeTrendBlock({ sample_size: 15 }),
      away_form: null,
      h2h: null,
    };
    render(<TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />);
    expect(screen.getByText("15 maç")).toBeDefined();
  });

  it("renders last N results as G/B/M dots", () => {
    const trends: TrendsData = {
      home_form: makeTrendBlock({ last_n_results: ["G", "G", "M", "B", "G"] }),
      away_form: null,
      h2h: null,
    };
    const { container } = render(
      <TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />,
    );
    const dots = container.querySelectorAll(".w-5.h-5.rounded");
    expect(dots.length).toBe(5);
    expect(screen.getAllByText("son 5").length).toBeGreaterThan(0);
  });

  it("displays win/draw/loss percentages", () => {
    const trends: TrendsData = {
      home_form: makeTrendBlock({ win_pct: 65, draw_pct: 20, loss_pct: 15 }),
      away_form: null,
      h2h: null,
    };
    render(<TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />);
    expect(screen.getAllByText("%65").length).toBeGreaterThan(0);
    expect(screen.getAllByText("%20").length).toBeGreaterThan(0);
    expect(screen.getAllByText("%15").length).toBeGreaterThan(0);
  });

  it("shows avg goals for/against", () => {
    const trends: TrendsData = {
      home_form: makeTrendBlock({ avg_goals_for: 2.3, avg_goals_against: 1.1 }),
      away_form: null,
      h2h: null,
    };
    render(<TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />);
    expect(screen.getByText("2.3 / 1.1")).toBeDefined();
  });

  it("renders metric labels", () => {
    const trends: TrendsData = {
      home_form: makeTrendBlock(),
      away_form: null,
      h2h: null,
    };
    render(<TrendsPanel trends={trends} homeTeam="Kayserispor" awayTeam="Karagumruk" />);
    expect(screen.getAllByText("Galibiyet").length).toBeGreaterThan(0);
    expect(screen.getAllByText("KG Var").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Üst 2.5").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Att / Yedi").length).toBeGreaterThan(0);
  });
});
