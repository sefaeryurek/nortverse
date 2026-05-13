import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCart, STORAGE_KEY, CART_EVENT } from "@/lib/cart";
import { makeCartItem } from "./fixtures";

// addItem yeni item'a addedAt: Date.now() yazıyor; testlerde deterministic değil.
// Karşılaştırma yaparken addedAt'i ignore ediyoruz.
function stripAddedAt<T extends { addedAt: number }>(item: T) {
  const { addedAt, ...rest } = item;
  return rest;
}

describe("useCart — initial state", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("boş localStorage → boş items, hydrated=true, count=0, jointProb=1, estOdds=0", () => {
    const { result } = renderHook(() => useCart());
    expect(result.current.items).toEqual([]);
    expect(result.current.hydrated).toBe(true);
    expect(result.current.count).toBe(0);
    expect(result.current.jointProb).toBe(1);
    expect(result.current.estOdds).toBe(0);
  });

  it("önceden dolu localStorage → mount sonrası items yüklenir", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([makeCartItem()]));
    const { result } = renderHook(() => useCart());
    expect(result.current.count).toBe(1);
    expect(result.current.items[0].matchId).toBe("2813084");
  });
});

describe("useCart — addItem", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("yeni item ekler, count artar", () => {
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(stripAddedAt(makeCartItem()));
    });
    expect(result.current.count).toBe(1);
    expect(result.current.items[0].matchId).toBe("2813084");
  });

  it("aynı (matchId+period+marketKey+selectionLabel) → idempotent (ikinci eklemez)", () => {
    const { result } = renderHook(() => useCart());
    const it = stripAddedAt(makeCartItem());
    act(() => {
      result.current.addItem(it);
      result.current.addItem(it);
    });
    expect(result.current.count).toBe(1);
  });

  it("farklı selectionLabel → her ikisi de eklenir", () => {
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(stripAddedAt(makeCartItem({ selectionLabel: "1" })));
      result.current.addItem(stripAddedAt(makeCartItem({ selectionLabel: "X" })));
    });
    expect(result.current.count).toBe(2);
  });

  it("addedAt timestamp atanır (recent)", () => {
    const before = Date.now();
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(stripAddedAt(makeCartItem()));
    });
    const after = Date.now();
    expect(result.current.items[0].addedAt).toBeGreaterThanOrEqual(before);
    expect(result.current.items[0].addedAt).toBeLessThanOrEqual(after);
  });
});

describe("useCart — removeItem", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("removeItem(idx: number) → ilgili indeksi siler", () => {
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(stripAddedAt(makeCartItem({ selectionLabel: "1" })));
      result.current.addItem(stripAddedAt(makeCartItem({ selectionLabel: "X" })));
    });
    act(() => {
      result.current.removeItem(0);
    });
    expect(result.current.count).toBe(1);
    expect(result.current.items[0].selectionLabel).toBe("X");
  });

  it("removeItem(key: string) → eşleşen key'i siler", () => {
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(stripAddedAt(makeCartItem({ selectionLabel: "1" })));
      result.current.addItem(stripAddedAt(makeCartItem({ selectionLabel: "X" })));
    });
    act(() => {
      result.current.removeItem("2813084|ft|result|X");
    });
    expect(result.current.count).toBe(1);
    expect(result.current.items[0].selectionLabel).toBe("1");
  });
});

describe("useCart — clear / has / hesaplar", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("clear() tüm items'i boşaltır", () => {
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(stripAddedAt(makeCartItem({ selectionLabel: "1" })));
      result.current.addItem(stripAddedAt(makeCartItem({ selectionLabel: "X" })));
    });
    expect(result.current.count).toBe(2);
    act(() => {
      result.current.clear();
    });
    expect(result.current.count).toBe(0);
    expect(result.current.items).toEqual([]);
  });

  it("has() — sepette varsa true, yoksa false", () => {
    const { result } = renderHook(() => useCart());
    const target = { matchId: "999", period: "ft" as const, marketKey: "kg", selectionLabel: "KG Var" };
    expect(result.current.has(target)).toBe(false);
    act(() => {
      result.current.addItem(stripAddedAt(makeCartItem({ ...target, marketLabel: "KG" })));
    });
    expect(result.current.has(target)).toBe(true);
  });

  it("jointProb ∏ (pct/100) — 3 leg %50/%60/%70 → 0.21", () => {
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(stripAddedAt(makeCartItem({ pct: 50, selectionLabel: "1" })));
      result.current.addItem(stripAddedAt(makeCartItem({ pct: 60, selectionLabel: "X", marketKey: "kg" })));
      result.current.addItem(stripAddedAt(makeCartItem({ pct: 70, selectionLabel: "Üst 2.5", marketKey: "ou_25" })));
    });
    expect(result.current.jointProb).toBeCloseTo(0.21, 3);
  });

  it("estOdds = 1/jointProb — 0.21 → ~4.76", () => {
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(stripAddedAt(makeCartItem({ pct: 50, selectionLabel: "1" })));
      result.current.addItem(stripAddedAt(makeCartItem({ pct: 60, selectionLabel: "X", marketKey: "kg" })));
      result.current.addItem(stripAddedAt(makeCartItem({ pct: 70, selectionLabel: "Üst 2.5", marketKey: "ou_25" })));
    });
    expect(result.current.estOdds).toBeCloseTo(1 / 0.21, 2);
  });
});

describe("useCart — storage event re-sync", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("CART_EVENT manuel dispatch → items re-fetch (cross-tab simulation)", () => {
    const { result } = renderHook(() => useCart());
    expect(result.current.count).toBe(0);

    // Başka bir tab/component localStorage'a yazdı + event dispatch etti
    act(() => {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify([makeCartItem()]));
      window.dispatchEvent(new CustomEvent(CART_EVENT));
    });

    expect(result.current.count).toBe(1);
    expect(result.current.items[0].matchId).toBe("2813084");
  });

  it("unmount sonrası event listener kaldırılır (memory leak yok)", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const { unmount } = renderHook(() => useCart());
    unmount();
    // useEffect cleanup'ı iki listener'ı (storage + CART_EVENT) çağırmalı
    const calls = removeSpy.mock.calls.map((c) => c[0]);
    expect(calls).toContain("storage");
    expect(calls).toContain(CART_EVENT);
    removeSpy.mockRestore();
  });
});
