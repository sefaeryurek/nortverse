import { expect, it, describe } from "vitest";
import { render, screen } from "@testing-library/react";
import ScoreList from "@/components/ScoreList";

describe("ScoreList", () => {
  it("renders all scores with count badge", () => {
    render(<ScoreList scores={["1-0", "2-0", "2-1"]} type="1" label="MS1" />);
    expect(screen.getByText("MS1")).toBeDefined();
    expect(screen.getByText("3")).toBeDefined();
    expect(screen.getByText("1-0")).toBeDefined();
    expect(screen.getByText("2-0")).toBeDefined();
    expect(screen.getByText("2-1")).toBeDefined();
  });

  it("renders dash when no scores", () => {
    render(<ScoreList scores={[]} type="x" label="MSX" />);
    expect(screen.getByText("MSX")).toBeDefined();
    expect(screen.getByText("0")).toBeDefined();
    expect(screen.getByText("—")).toBeDefined();
  });

  it("renders single score", () => {
    render(<ScoreList scores={["0-0"]} type="x" label="MSX" />);
    expect(screen.getByText("1")).toBeDefined();
    expect(screen.getByText("0-0")).toBeDefined();
  });

  it("renders MS2 type scores", () => {
    render(<ScoreList scores={["0-1", "0-2"]} type="2" label="MS2" />);
    expect(screen.getByText("MS2")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
    expect(screen.getByText("0-1")).toBeDefined();
    expect(screen.getByText("0-2")).toBeDefined();
  });
});
