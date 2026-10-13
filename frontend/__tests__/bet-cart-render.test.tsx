import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import BetCart from "@/components/BetCart";
import { STORAGE_KEY, CART_EVENT } from "@/lib/cart";
import type { CartItem } from "@/lib/cart";

HTMLDialogElement.prototype.showModal = vi.fn();
HTMLDialogElement.prototype.close = vi.fn();

afterEach(cleanup);

function makeItem(overrides: Partial<CartItem> = {}): CartItem {
  return {
    matchId: "123",
    homeTeam: "Galatasaray",
    awayTeam: "Fenerbahce",
    period: "ft",
    marketKey: "result",
    marketLabel: "MS Sonuç",
    selectionLabel: "MS 1",
    pct: 72,
    archive: "archive_1",
    addedAt: Date.now(),
    ...overrides,
  };
}

function setCart(items: CartItem[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  window.dispatchEvent(new CustomEvent(CART_EVENT));
}

beforeEach(() => {
  localStorage.removeItem(STORAGE_KEY);
});

describe("BetCart", () => {
  it("renders nothing when cart is empty", () => {
    const { container } = render(<BetCart />);
    expect(container.innerHTML).toBe("");
  });

  it("shows floating button with count when cart has items", () => {
    setCart([makeItem()]);
    render(<BetCart />);
    const buttons = screen.getAllByLabelText(/Bahis sepetini aç/);
    expect(buttons.length).toBeGreaterThan(0);
  });

  it("shows count badge", () => {
    setCart([makeItem(), makeItem({ matchId: "456", marketKey: "over_25" })]);
    render(<BetCart />);
    const badges = screen.getAllByText("2");
    expect(badges.length).toBeGreaterThan(0);
  });

  it("opens dialog on floating button click", () => {
    setCart([makeItem()]);
    render(<BetCart />);
    const buttons = screen.getAllByLabelText(/Bahis sepetini aç/);
    fireEvent.click(buttons[0]);
    expect(screen.getByText("Bahis Sepeti")).toBeTruthy();
  });

  it("shows item details in open panel", () => {
    setCart([makeItem()]);
    render(<BetCart />);
    const buttons = screen.getAllByLabelText(/Bahis sepetini aç/);
    fireEvent.click(buttons[0]);
    expect(screen.getByText("MS 1")).toBeTruthy();
    expect(screen.getByText("MS Sonuç")).toBeTruthy();
    expect(screen.getByText(/Galatasaray/)).toBeTruthy();
  });

  it("shows period badge", () => {
    setCart([makeItem({ period: "ht" })]);
    render(<BetCart />);
    const buttons = screen.getAllByLabelText(/Bahis sepetini aç/);
    fireEvent.click(buttons[0]);
    expect(screen.getByText("İY")).toBeTruthy();
  });

  it("shows pct value", () => {
    setCart([makeItem({ pct: 72 })]);
    render(<BetCart />);
    const buttons = screen.getAllByLabelText(/Bahis sepetini aç/);
    fireEvent.click(buttons[0]);
    expect(screen.getByText("%72")).toBeTruthy();
  });

  it("has clear button", () => {
    setCart([makeItem()]);
    render(<BetCart />);
    const buttons = screen.getAllByLabelText(/Bahis sepetini aç/);
    fireEvent.click(buttons[0]);
    expect(screen.getByText("Sepeti Temizle")).toBeTruthy();
  });

  it("has close button", () => {
    setCart([makeItem()]);
    render(<BetCart />);
    const openBtns = screen.getAllByLabelText(/Bahis sepetini aç/);
    fireEvent.click(openBtns[0]);
    expect(screen.getByLabelText("Sepeti kapat")).toBeTruthy();
  });

  it("shows disclaimer text", () => {
    setCart([makeItem()]);
    render(<BetCart />);
    const buttons = screen.getAllByLabelText(/Bahis sepetini aç/);
    fireEvent.click(buttons[0]);
    expect(screen.getByText(/geçmiş arşiv eşleşmelerinin sıklığıdır/)).toBeTruthy();
  });

  it("mobile bar shows item count text", () => {
    setCart([makeItem()]);
    render(<BetCart />);
    expect(screen.getByText("1 seçim")).toBeTruthy();
  });
});
