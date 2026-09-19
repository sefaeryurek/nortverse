import { expect, it, describe, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import DayTabs from "@/components/DayTabs";

afterEach(() => { cleanup(); });

describe("DayTabs render", () => {
  it("renders 8 days with the active day marked", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    expect(screen.getAllByRole("link")).toHaveLength(7);
    expect(document.querySelector('[aria-current="date"]')).not.toBeNull();
  });

  it("active date does not navigate", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    const active = document.querySelector('[aria-current="date"]');
    expect(active?.tagName).toBe("SPAN");
    expect(active?.textContent).toContain("09/15");
  });

  it("non-active date has a real link", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    expect(screen.getAllByRole("link")[0].getAttribute("href")).toContain("/bulten?date=");
  });

  it("uses custom basePath", () => {
    render(<DayTabs activeDate="2026-09-15" basePath="/sonuclar" referenceDate="2026-09-15" />);
    expect(screen.getAllByRole("link")[0].getAttribute("href")).toContain("/sonuclar?date=");
  });

  it("shows Turkish day names", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    const dayNames = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
    const days = [...screen.getAllByRole("link"), document.querySelector('[aria-current="date"]')!];
    days.forEach((day) => {
      const text = day.textContent!;
      const found = dayNames.some((d) => text.includes(d));
      expect(found).toBe(true);
    });
  });

  it("shows date portion in MM/DD format", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    expect(screen.getByText("09/15")).toBeDefined();
  });
});
