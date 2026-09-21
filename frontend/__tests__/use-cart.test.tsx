import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCart, STORAGE_KEY, CART_EVENT } from "@/lib/cart";
import { makeCartItem } from "./fixtures";

// addItem yeni item'a addedAt: Date.now() yazıyor; testlerde deterministic değil.
// Karşılaştırma yaparken addedAt'i ignore ediyoruz.
function stripAddedAt<T extends { addedAt: number }>(item: T) {
  const { addedAt, ...rest } = item;
  void addedAt;
  return rest;
}

describe("useCart — initial state", () => {
  it("keeps multiple hook instances synchronized when storage writes fail", () => {
    const first = renderHook(() => useCart());
    const second = renderHook(() => useCart());
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota"); });
    try {
      act(() => first.result.current.addItem(makeCartItem()));
      expect(second.result.current.count).toBe(1);
      act(() => second.result.current.addItem(makeCartItem({ matchId: "999" })));
      expect(first.result.current.count).toBe(2);
    } finally {
      spy.mockRestore();
      act(() => first.result.current.clear());
    }
  });
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("boş localStorage → boş items, hydrated=true, count=0", () => {
    const { result } = renderHook(() => useCart());
    expect(result.current.items).toEqual([]);
    expect(result.current.hydrated).toBe(true);
    expect(result.current.count).toBe(0);
  });

  it("önceden dolu localStorage → mount sonrası items yüklenir", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([makeCartItem()]));
    const { result } = renderHook(() => useCart());
    expect(result.current.count).toBe(1);
    expect(result.current.items[0].matchId).toBe("2813084");
  });
});

describe("useCart — addItem", () => {
  it("replaces the previous option in the same match, period and market", () => {
    window.localStorage.clear();
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(makeCartItem());
      result.current.addItem(makeCartItem({ selectionLabel: "X" }));
    });
    expect(result.current.items.map((x) => x.selectionLabel)).toEqual(["X"]);
  });
  it("keeps selections from different periods of the same match", () => {
    window.localStorage.clear();
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(makeCartItem());
      result.current.addItem(makeCartItem({ period: "ht" }));
    });
    expect(result.current.count).toBe(2);
    expect(result.current.items.map((item) => item.period)).toEqual(["ft", "ht"]);
  });
  it("keeps a zero archive frequency as recorded", () => {
    window.localStorage.clear();
    const { result } = renderHook(() => useCart());
    act(() => result.current.addItem(makeCartItem({ pct: 0 })));
    expect(result.current.items[0].pct).toBe(0);
  });
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

  it("farklı maçlar → her ikisi de eklenir", () => {
    const { result } = renderHook(() => useCart());
    act(() => {
      result.current.addItem(stripAddedAt(makeCartItem({ selectionLabel: "1" })));
      result.current.addItem(stripAddedAt(makeCartItem({ matchId: "999", selectionLabel: "X" })));
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
      result.current.addItem(stripAddedAt(makeCartItem({ matchId: "999", selectionLabel: "X" })));
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
      result.current.addItem(stripAddedAt(makeCartItem({ matchId: "999", selectionLabel: "X" })));
    });
    act(() => {
      result.current.removeItem("999|ft|result|X");
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
      result.current.addItem(stripAddedAt(makeCartItem({ matchId: "999", selectionLabel: "X" })));
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
