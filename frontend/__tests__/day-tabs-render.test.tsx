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

  it("shows past dates on the results page", () => {
    render(<DayTabs activeDate="2026-09-15" basePath="/sonuclar" referenceDate="2026-09-15" range="past" />);
    expect(screen.getByText("09/08")).toBeDefined();
    expect(screen.getByText("09/15")).toBeDefined();
    expect(screen.queryByText("09/16")).toBeNull();
    expect(document.querySelector('[aria-current="date"]')?.parentElement?.firstElementChild)
      .toBe(document.querySelector('[aria-current="date"]'));
  });

  it("defaults results navigation to today and the previous seven days", () => {
    render(<DayTabs activeDate="2026-09-16" basePath="/sonuclar" referenceDate="2026-09-16" />);
    expect(screen.getByRole("navigation", { name: "Sonuç tarihleri: bugün ve önceki 7 gün" })).toBeDefined();
    expect(screen.getByText("09/09")).toBeDefined();
    expect(screen.getByText("09/15")).toBeDefined();
    expect(screen.queryByText("09/17")).toBeNull();
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
