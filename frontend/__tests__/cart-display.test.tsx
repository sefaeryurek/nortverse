import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import BetCart from "@/components/BetCart";
import { STORAGE_KEY, writeStorage } from "@/lib/cart";
import { makeCartItem } from "./fixtures";

const originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "showModal");
beforeEach(() => {
  window.localStorage.clear();
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute("open", ""); },
  });
  vi.stubGlobal("matchMedia", () => ({ matches: true }));
});
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals();
  if (originalShowModal) Object.defineProperty(HTMLDialogElement.prototype, "showModal", originalShowModal);
  else Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
});

describe("cart probability display", () => {
  it("closes on cancel and returns focus to the opening control", () => {
    writeStorage([makeCartItem()]);
    render(<BetCart />);
    fireEvent.click(screen.getAllByRole("button", { name: "Bahis sepetini aç (1 tahmin)" })[0]);
    fireEvent(screen.getByRole("dialog", { name: "Bahis Sepeti" }), new Event("cancel"));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(screen.getAllByRole("button", { name: "Bahis sepetini aç (1 tahmin)" })[0]);
  });

  it("does not reopen automatically after the last item is removed", () => {
    writeStorage([makeCartItem()]);
    render(<BetCart />);
    fireEvent.click(screen.getAllByRole("button", { name: "Bahis sepetini aç (1 tahmin)" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Tahmini sepetten kaldır" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    act(() => writeStorage([makeCartItem({ matchId: "999" })]));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getAllByRole("button", { name: "Bahis sepetini aç (1 tahmin)" }).length).toBeGreaterThan(0);
  });
  it("same-match selections show correlation-corrected probability", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([
      makeCartItem({ pct: 80 }),
      makeCartItem({ marketKey: "kg", selectionLabel: "KG Var", pct: 75 }),
    ]));
    render(<BetCart />);
    fireEvent.click(screen.getAllByRole("button", { name: "Bahis sepetini aç (2 tahmin)" })[0]);
    expect(screen.getByRole("status").textContent).toContain("korelasyon düzeltmesiyle");
  });

  it("different-match selections show joint probability", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([
      makeCartItem({ pct: 80 }), makeCartItem({ matchId: "2", pct: 75 }),
    ]));
    render(<BetCart />);
    fireEvent.click(screen.getAllByRole("button", { name: "Bahis sepetini aç (2 tahmin)" })[0]);
    expect(screen.getByText("≈%60.0")).toBeDefined();
    expect(screen.getByRole("status").textContent).toContain("korelasyon düzeltmesiyle");
  });
});
