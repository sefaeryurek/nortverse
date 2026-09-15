// Bahis sepeti — localStorage tabanlı, çok-maç destekli.
// Kullanıcı farklı maçlardan tahminleri biriktirip kombo oranı görebilir.

"use client";

import { useSyncExternalStore, useMemo, useCallback } from "react";
import type { Period } from "./labels";
import { getCorrectionFactor } from "./correlations";

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

export const STORAGE_KEY = "nortverse_bet_cart";
export const CART_EVENT = "nortverse-cart-updated";
let memoryItems: CartItem[] = [];
let storageFailed = false;

function subscribe(listener: () => void) {
  window.addEventListener("storage", listener);
  window.addEventListener(CART_EVENT, listener);
  return () => {
    window.removeEventListener("storage", listener);
    window.removeEventListener(CART_EVENT, listener);
  };
}

const getSnapshot = () => JSON.stringify(readStorage());
const getServerSnapshot = () => null;

// Helper'lar test edilebilirlik için export edildi (Sprint 10 Faz B).
// Production'da useCart hook'u içinde tüketilirler.
export function readStorage(): CartItem[] {
  if (typeof window === "undefined") return [];
  if (storageFailed) return memoryItems;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (x): x is CartItem =>
        x && typeof x === "object" &&
        [x.matchId, x.marketKey, x.homeTeam, x.awayTeam, x.selectionLabel, x.marketLabel]
          .every((value) => typeof value === "string" && value.trim().length > 0) &&
        typeof x.pct === "number" && Number.isFinite(x.pct) && x.pct >= 0 && x.pct <= 100 &&
        ["A", "B", "AB"].includes(x.archive) && ["ht", "h2", "ft"].includes(x.period) &&
        typeof x.addedAt === "number" && Number.isFinite(x.addedAt),
    );
  } catch {
    return memoryItems;
  }
}

export function writeStorage(items: CartItem[]): void {
  if (typeof window === "undefined") return;
  memoryItems = items;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    storageFailed = false;
  } catch {
    storageFailed = true;
  }
  window.dispatchEvent(new CustomEvent(CART_EVENT));
}

export function itemKey(it: Pick<CartItem, "matchId" | "marketKey" | "selectionLabel" | "period">): string {
  return `${it.matchId}|${it.period}|${it.marketKey}|${it.selectionLabel}`;
}

/**
 * React hook: localStorage senkron sepet state.
 * Cross-tab senkronizasyon: storage event + custom event.
 */
export function useCart() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const hydrated = snapshot !== null;
  const items = useMemo<CartItem[]>(() => snapshot === null ? [] : JSON.parse(snapshot), [snapshot]);

  const addItem = useCallback((it: Omit<CartItem, "addedAt">) => {
    const cur = readStorage();
    const k = itemKey(it);
    if (cur.some((x) => itemKey(x) === k)) return; // idempotent
    // A market is a choice: selecting another option replaces the old one.
    const next = [...cur.filter((x) => !(x.matchId === it.matchId && x.period === it.period &&
      x.marketKey === it.marketKey)), { ...it, addedAt: Date.now() }];
    writeStorage(next);
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
  }, []);

  const clear = useCallback(() => {
    writeStorage([]);
  }, []);

  const has = useCallback(
    (it: Pick<CartItem, "matchId" | "marketKey" | "selectionLabel" | "period">) => {
      const k = itemKey(it);
      return items.some((x) => itemKey(x) === k);
    },
    [items],
  );

  const jointProb = useMemo(() => {
    if (items.length === 0) return null;
    let prob = 1;
    for (const it of items) {
      prob *= it.pct / 100;
    }
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        if (items[i].matchId === items[j].matchId) {
          const corr = getCorrectionFactor(
            items[i].marketKey, items[i].selectionLabel,
            items[j].marketKey, items[j].selectionLabel,
          );
          prob *= corr;
        }
      }
    }
    return Math.max(0, Math.min(1, prob));
  }, [items]);
  const estOdds = items.length === 0 ? 0 : jointProb === null || jointProb === 0 ? null : 1 / jointProb;

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
