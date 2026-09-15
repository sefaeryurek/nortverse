import { expect, it, describe, vi, afterEach } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import DayTabs from "@/components/DayTabs";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));

afterEach(() => { cleanup(); pushMock.mockClear(); });

describe("DayTabs render", () => {
  it("renders 8 day buttons", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(8);
  });

  it("active date button is disabled", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    const buttons = screen.getAllByRole("button");
    const active = buttons.find((b) => b.getAttribute("disabled") !== null);
    expect(active).toBeDefined();
    expect(active!.textContent).toContain("09/15");
  });

  it("non-active button navigates on click", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    const buttons = screen.getAllByRole("button");
    const nonActive = buttons.find((b) => b.getAttribute("disabled") === null)!;
    fireEvent.click(nonActive);
    expect(pushMock).toHaveBeenCalledTimes(1);
    expect(pushMock.mock.calls[0][0]).toContain("/bulten?date=");
  });

  it("uses custom basePath", () => {
    render(<DayTabs activeDate="2026-09-15" basePath="/sonuclar" referenceDate="2026-09-15" />);
    const buttons = screen.getAllByRole("button");
    const nonActive = buttons.find((b) => b.getAttribute("disabled") === null)!;
    fireEvent.click(nonActive);
    expect(pushMock.mock.calls[0][0]).toContain("/sonuclar?date=");
  });

  it("clicking active date does not navigate", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    const buttons = screen.getAllByRole("button");
    const active = buttons.find((b) => b.getAttribute("disabled") !== null)!;
    fireEvent.click(active);
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("shows Turkish day names", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    const dayNames = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
    const buttons = screen.getAllByRole("button");
    buttons.forEach((btn) => {
      const text = btn.textContent!;
      const found = dayNames.some((d) => text.includes(d));
      expect(found).toBe(true);
    });
  });

  it("shows date portion in MM/DD format", () => {
    render(<DayTabs activeDate="2026-09-15" referenceDate="2026-09-15" />);
    expect(screen.getByText("09/15")).toBeDefined();
  });
});
