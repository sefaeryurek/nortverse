import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

// Canlı kapsama karnesi (Sprint 94 C4)
const api = vi.hoisted(() => ({ getLiveCoverage: vi.fn() }));
vi.mock("@/lib/api", () => api);

import LiveCoverage from "@/components/LiveCoverage";
import { getDictionary } from "@/lib/i18n";

afterEach(() => { cleanup(); vi.clearAllMocks(); });
const t = getDictionary("tr");

it("shows recorded share and missed matches", async () => {
  api.getLiveCoverage.mockResolvedValue({ days: 7, reached_ht: 61, frozen: 53, pct: 86.9, missed: [
    { match_id: "1", home_team: "Aston Villa", away_team: "Wolves", league_name: "English Premier League", kickoff_time: "2026-10-26T14:00:00+00:00" },
  ] });
  render(await LiveCoverage({ t, scope: "main" }));
  expect(screen.getByText(/61 izlenen maçın 53'inde/)).toBeTruthy();
  expect(screen.getByText("Aston Villa - Wolves")).toBeTruthy();
});

it("renders nothing on error or when no match reached half-time", async () => {
  api.getLiveCoverage.mockRejectedValueOnce(new Error("x"));
  expect(await LiveCoverage({ t, scope: "main" })).toBeNull();
  api.getLiveCoverage.mockResolvedValueOnce({ days: 7, reached_ht: 0, frozen: 0, pct: null, missed: [] });
  expect(await LiveCoverage({ t, scope: "main" })).toBeNull();
});
