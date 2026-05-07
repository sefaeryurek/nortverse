"use client";

import { useCart, type CartItem } from "@/lib/cart";

interface Props {
  item: Omit<CartItem, "addedAt">;
  size?: "sm" | "md";
  className?: string;
}

/**
 * Tek tahmin için "+" / "✓" toggle butonu.
 * Sepete ekle/çıkar — idempotent.
 */
export default function AddToCartButton({ item, size = "sm", className }: Props) {
  const { addItem, removeItem, has, hydrated } = useCart();
  const inCart = hydrated && has(item);
  const dim = size === "sm" ? "w-5 h-5 text-[10px]" : "w-6 h-6 text-xs";

  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (inCart) {
          removeItem(`${item.matchId}|${item.period}|${item.marketKey}|${item.selectionLabel}`);
        } else {
          addItem(item);
        }
      }}
      className={`${dim} rounded flex items-center justify-center font-bold transition-all ${className ?? ""}`}
      style={{
        backgroundColor: inCart ? "#16a34a" : "#1e293b",
        color: inCart ? "#ecfdf5" : "#94a3b8",
        border: `1px solid ${inCart ? "#15803d" : "#334155"}`,
      }}
      aria-label={inCart ? "Sepetten çıkar" : "Sepete ekle"}
      title={inCart ? "Sepetten çıkar" : "Sepete ekle"}
    >
      {inCart ? "✓" : "+"}
    </button>
  );
}
