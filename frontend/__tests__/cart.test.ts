import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  readStorage,
  writeStorage,
  itemKey,
  STORAGE_KEY,
  CART_EVENT,
  type CartItem,
} from "@/lib/cart";

function makeItem(overrides: Partial<CartItem> = {}): CartItem {
  return {
    matchId: "2813084",
    homeTeam: "Kayserispor",
    awayTeam: "Karagumruk",
    marketKey: "result",
    selectionLabel: "1",
    marketLabel: "Maç Sonucu",
    pct: 70,
    archive: "A",
    period: "ft",
    addedAt: 1700000000000,
    ...overrides,
  };
}

describe("readStorage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("storage boş → boş array", () => {
    expect(readStorage()).toEqual([]);
  });

  it("bozuk JSON → boş array (graceful)", () => {
    window.localStorage.setItem(STORAGE_KEY, "{not json");
    expect(readStorage()).toEqual([]);
  });

  it("array dışı veri (obje) → boş array", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ matchId: "x" }));
    expect(readStorage()).toEqual([]);
  });

  it("geçerli array → CartItem[] döner", () => {
    const items = [makeItem(), makeItem({ matchId: "999", selectionLabel: "X" })];
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    const out = readStorage();
    expect(out).toHaveLength(2);
    expect(out[0].matchId).toBe("2813084");
    expect(out[1].matchId).toBe("999");
  });

  it("eksik field'lı item filtrelenir (matchId yoksa)", () => {
    const items = [
      makeItem(),
      { marketKey: "result", selectionLabel: "1" }, // matchId yok → at
      makeItem({ matchId: "999" }),
    ];
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    const out = readStorage();
    expect(out).toHaveLength(2);
  });

  it("string olmayan matchId filtrelenir", () => {
    const items = [makeItem(), { matchId: 12345, marketKey: "result" }];
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    expect(readStorage()).toHaveLength(1);
  });
});

describe("writeStorage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("items'i localStorage'a JSON olarak yazar", () => {
    const items = [makeItem()];
    writeStorage(items);
    const raw = window.localStorage.getItem(STORAGE_KEY);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!)).toEqual(items);
  });

  it("CartItem CustomEvent fırlatır (cross-tab sync için)", () => {
    const handler = vi.fn();
    window.addEventListener(CART_EVENT, handler);
    try {
      writeStorage([makeItem()]);
      expect(handler).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener(CART_EVENT, handler);
    }
  });

  it("boş array → storage temizlenir (boş JSON)", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify([makeItem()]));
    writeStorage([]);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("[]");
  });
});

describe("itemKey", () => {
  it("deterministic: aynı input → aynı output", () => {
    const k1 = itemKey({ matchId: "1", period: "ft", marketKey: "result", selectionLabel: "1" });
    const k2 = itemKey({ matchId: "1", period: "ft", marketKey: "result", selectionLabel: "1" });
    expect(k1).toBe(k2);
  });

  it("farklı period → farklı key (aynı maç içinde IY ve MS ayrı)", () => {
    const ht = itemKey({ matchId: "1", period: "ht", marketKey: "result", selectionLabel: "1" });
    const ft = itemKey({ matchId: "1", period: "ft", marketKey: "result", selectionLabel: "1" });
    expect(ht).not.toBe(ft);
  });

  it("farklı selectionLabel → farklı key (1 ve X ayrı)", () => {
    const a = itemKey({ matchId: "1", period: "ft", marketKey: "result", selectionLabel: "1" });
    const b = itemKey({ matchId: "1", period: "ft", marketKey: "result", selectionLabel: "X" });
    expect(a).not.toBe(b);
  });

  it("format: matchId|period|marketKey|selectionLabel", () => {
    const k = itemKey({
      matchId: "2813084",
      period: "ft",
      marketKey: "kg",
      selectionLabel: "KG Var",
    });
    expect(k).toBe("2813084|ft|kg|KG Var");
  });
});

describe("readStorage + writeStorage roundtrip", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("yazılan veri tekrar okunduğunda aynı içeriği döner", () => {
    const items = [
      makeItem(),
      makeItem({ matchId: "999", marketKey: "kg", selectionLabel: "KG Var", period: "ht" }),
    ];
    writeStorage(items);
    expect(readStorage()).toEqual(items);
  });
});
