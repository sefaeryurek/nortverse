import { expect, it, describe, vi, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import AddToCartButton from "@/components/AddToCartButton";
import { MatchProvider } from "@/lib/match-context";
import { STORAGE_KEY } from "@/lib/cart";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

beforeEach(() => { window.localStorage.clear(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const item = {
  matchId: "2813084",
  homeTeam: "Kayserispor",
  awayTeam: "Karagumruk",
  marketKey: "result",
  marketLabel: "Maç Sonucu",
  selectionLabel: "1",
  pct: 70,
  archive: "A" as const,
  period: "ft" as const,
};

function renderWithContext(ui: React.ReactElement) {
  return render(
    <MatchProvider value={{ matchId: "2813084", homeTeam: "Kayserispor", awayTeam: "Karagumruk" }}>
      {ui}
    </MatchProvider>,
  );
}

describe("AddToCartButton", () => {
  it("renders + when item is not in cart", () => {
    renderWithContext(<AddToCartButton item={item} />);
    expect(screen.getByText("+")).toBeDefined();
    expect(screen.getByLabelText("Sepete ekle")).toBeDefined();
  });

  it("adds item to cart on click", () => {
    renderWithContext(<AddToCartButton item={item} />);
    fireEvent.click(screen.getByText("+"));
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    expect(stored.length).toBe(1);
    expect(stored[0].matchId).toBe("2813084");
  });

  it("shows checkmark after adding", () => {
    renderWithContext(<AddToCartButton item={item} />);
    fireEvent.click(screen.getByText("+"));
    expect(screen.getByText("✓")).toBeDefined();
    expect(screen.getByLabelText("Sepetten çıkar")).toBeDefined();
  });

  it("removes item from cart on second click", () => {
    renderWithContext(<AddToCartButton item={item} />);
    fireEvent.click(screen.getByText("+"));
    fireEvent.click(screen.getByText("✓"));
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    expect(stored.length).toBe(0);
  });

  it("prevents event propagation on click", () => {
    const parentClick = vi.fn();
    renderWithContext(
      <div onClick={parentClick}>
        <AddToCartButton item={item} />
      </div>,
    );
    fireEvent.click(screen.getByText("+"));
    expect(parentClick).not.toHaveBeenCalled();
  });

  it("renders sm size by default", () => {
    renderWithContext(<AddToCartButton item={item} />);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("w-5");
  });

  it("renders md size when specified", () => {
    renderWithContext(<AddToCartButton item={item} size="md" />);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("w-6");
  });
});
