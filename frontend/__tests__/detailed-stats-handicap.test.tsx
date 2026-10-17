import { afterEach, beforeEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import DetailedStats from "@/components/DetailedStats";
import { makePatternResult } from "./fixtures";

beforeEach(() => { window.localStorage.setItem("nortverse_detailed_open", "1"); });
afterEach(() => { cleanup(); window.localStorage.clear(); });

// Backend: hnd_h20 = ev +2 başlar = "(2:0)", hnd_a20 = deplasman +2 = "(0:2)".
it.each([
  ["hnd_h20_1_pct", 91, "Hnd (2:0)"],
  ["hnd_h10_1_pct", 82, "Hnd (1:0)"],
  ["hnd_a10_1_pct", 73, "Hnd (0:1)"],
  ["hnd_a20_1_pct", 64, "Hnd (0:2)"],
] as const)("%s is shown under %s", (field, value, label) => {
  const pattern = makePatternResult({
    match_count: 30,
    hnd_h20_1_pct: 1, hnd_h10_1_pct: 2, hnd_a10_1_pct: 3, hnd_a20_1_pct: 4,
    [field]: value,
  });
  render(<DetailedStats patternB={pattern} patternC={null} patternD={null} period="ft" />);
  const cell = screen.getByText(`%${value}`).parentElement;
  expect(cell?.textContent).toContain(label);
});
