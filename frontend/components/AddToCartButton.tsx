"use client";

import { useCart, type CartItem } from "@/lib/cart";

interface Props {
  item: Omit<CartItem, "addedAt">;
  size?: "sm" | "md";
  className?: string;
}

/**
 * Tek tahmin icin "+" / check toggle butonu.
 * Sepete ekle/cikar -- idempotent.
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
      className={`${dim} rounded-full flex items-center justify-center font-bold transition-all ${className ?? ""}`}
      style={{
        backgroundColor: inCart ? "var(--nv-accent-green)" : "var(--nv-bg-elevated)",
        color: inCart ? "var(--nv-text-inverse)" : "var(--nv-text-secondary)",
        border: `1px solid ${inCart ? "var(--nv-accent-green)" : "var(--nv-border-accent)"}`,
        transitionDuration: "var(--nv-duration-normal)",
        transitionTimingFunction: "var(--nv-ease)",
      }}
      aria-label={inCart ? "Sepetten çıkar" : "Sepete ekle"}
      title={inCart ? "Sepetten çıkar" : "Sepete ekle"}
    >
      {inCart ? "✓" : "+"}
    </button>
  );
}
