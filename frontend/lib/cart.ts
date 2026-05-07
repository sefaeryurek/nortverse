// Bahis sepeti — localStorage tabanlı, çok-maç destekli.
// Kullanıcı farklı maçlardan tahminleri biriktirip kombo oranı görebilir.

"use client";

import { useEffect, useState, useCallback } from "react";
import type { Period } from "./labels";

export interface CartItem {
  matchId: string;
  homeTeam: string;
  awayTeam: string;
  marketKey: string;
  selectionLabel: string;
  marketLabel: string;
  pct: number;
  archive: "A" | "B" | "AB";
  period: Period;
  addedAt: number;
}

const STORAGE_KEY = "nortverse_bet_cart";
const CART_EVENT = "nortverse-cart-updated";

function readStorage(): CartItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (x): x is CartItem =>
        x && typeof x === "object" && typeof x.matchId === "string" && typeof x.marketKey === "string",
    );
  } catch {
    return [];
  }
}

function writeStorage(items: CartItem[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    window.dispatchEvent(new CustomEvent(CART_EVENT));
  } catch {
    /* quota / disabled — sessizce yut */
  }
}

function itemKey(it: Pick<CartItem, "matchId" | "marketKey" | "selectionLabel" | "period">): string {
  return `${it.matchId}|${it.period}|${it.marketKey}|${it.selectionLabel}`;
}

/**
 * React hook: localStorage senkron sepet state.
 * Cross-tab senkronizasyon: storage event + custom event.
 */
export function useCart() {
  const [items, setItems] = useState<CartItem[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setItems(readStorage());
    setHydrated(true);

    const sync = () => setItems(readStorage());
    window.addEventListener("storage", sync);
    window.addEventListener(CART_EVENT, sync as EventListener);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(CART_EVENT, sync as EventListener);
    };
  }, []);

  const addItem = useCallback((it: Omit<CartItem, "addedAt">) => {
    const cur = readStorage();
    const k = itemKey(it);
    if (cur.some((x) => itemKey(x) === k)) return; // idempotent
    const next = [...cur, { ...it, addedAt: Date.now() }];
    writeStorage(next);
    setItems(next);
  }, []);

  const removeItem = useCallback((idxOrKey: number | string) => {
    const cur = readStorage();
    let next: CartItem[];
    if (typeof idxOrKey === "number") {
      next = cur.filter((_, i) => i !== idxOrKey);
    } else {
      next = cur.filter((x) => itemKey(x) !== idxOrKey);
    }
    writeStorage(next);
    setItems(next);
  }, []);

  const clear = useCallback(() => {
    writeStorage([]);
    setItems([]);
  }, []);

  const has = useCallback(
    (it: Pick<CartItem, "matchId" | "marketKey" | "selectionLabel" | "period">) => {
      const k = itemKey(it);
      return items.some((x) => itemKey(x) === k);
    },
    [items],
  );

  // Joint olasılık (bağımsızlık varsayımı) ve tahmini kombi oran
  const jointProb = items.reduce((acc, x) => acc * (x.pct / 100), 1);
  const estOdds = items.length === 0 ? 0 : 1 / Math.max(jointProb, 1e-9);

  return {
    items,
    hydrated,
    addItem,
    removeItem,
    clear,
    has,
    jointProb,
    estOdds,
    count: items.length,
  };
}

export { itemKey, STORAGE_KEY as CART_STORAGE_KEY };
