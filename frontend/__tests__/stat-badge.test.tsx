import { expect, it, describe } from "vitest";
import { render, screen } from "@testing-library/react";
import StatBadge from "@/components/StatBadge";

describe("StatBadge", () => {
  it("renders rounded percentage", () => {
    render(<StatBadge value={72.6} />);
    expect(screen.getByText("73%")).toBeDefined();
  });

  it("renders label when provided", () => {
    render(<StatBadge value={80} label="Galibiyet" />);
    expect(screen.getByText("80%")).toBeDefined();
    expect(screen.getByText("Galibiyet")).toBeDefined();
  });

  it("renders 0%", () => {
    render(<StatBadge value={0} />);
    expect(screen.getByText("0%")).toBeDefined();
  });

  it("renders 100%", () => {
    render(<StatBadge value={100} />);
    expect(screen.getByText("100%")).toBeDefined();
  });

  it("rounds down fractional values", () => {
    render(<StatBadge value={49.4} />);
    expect(screen.getByText("49%")).toBeDefined();
  });

  it("accepts sm size", () => {
    const { container } = render(<StatBadge value={65} size="sm" />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.className).toContain("text-xs");
  });

  it("accepts md size", () => {
    const { container } = render(<StatBadge value={65} size="md" />);
    const el = container.firstElementChild as HTMLElement;
    expect(el.className).toContain("text-sm");
  });
});
