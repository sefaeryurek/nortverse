"use client";

import { useEffect, useRef, useState } from "react";
import { itemKey, useCart } from "@/lib/cart";

function PeriodBadge({ period }: { period: "ht" | "h2" | "ft" }) {
  const label = period === "ht" ? "İY" : period === "h2" ? "2Y" : "MS";
  return (
    <span
      className="nv-badge"
      style={{
        backgroundColor: "var(--nv-bg-elevated)",
        color: "var(--nv-text-secondary)",
        fontSize: "8px",
      }}
    >
      {label}
    </span>
  );
}

export default function BetCart() {
  const cart = useCart();
  return cart.hydrated && cart.count > 0 ? <PopulatedCart cart={cart} /> : null;
}

function PopulatedCart({ cart }: { cart: ReturnType<typeof useCart> }) {
  const { items, removeItem, clear, count } = cart;
  const [open, setOpen] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const desktopTrigger = useRef<HTMLButtonElement>(null);
  const mobileTrigger = useRef<HTMLButtonElement>(null);
  const restoreFocus = useRef(false);

  useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
      restoreFocus.current = true;
    } else if (restoreFocus.current) {
      const trigger = window.matchMedia("(min-width: 768px)").matches ? desktopTrigger : mobileTrigger;
      trigger.current?.focus();
      restoreFocus.current = false;
    }
  }, [open]);

  return (
    <>
      {/* Floating buton -- sadece desktop (md+); mobile'de sticky bar ile degistirildi */}
      {!open && (
        <button
          ref={desktopTrigger}
          onClick={() => setOpen(true)}
          className="fixed bottom-4 right-4 z-40 hidden md:flex items-center gap-2 px-4 py-3 transition-transform"
          style={{
            backgroundColor: "var(--nv-accent-green)",
            color: "var(--nv-text-inverse)",
            borderRadius: "var(--nv-radius-full)",
            boxShadow: "var(--nv-shadow-glow-green), var(--nv-shadow-lg)",
            transitionDuration: "var(--nv-duration-normal)",
            transitionTimingFunction: "var(--nv-ease)",
          }}
          aria-label={`Bahis sepetini aç (${count} tahmin)`}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <span className="text-sm font-bold">Sepet</span>
          <span
            className="nv-badge"
            style={{
              backgroundColor: "var(--nv-accent-green-dim)",
              color: "var(--nv-accent-green)",
            }}
          >
            {count}
          </span>
        </button>
      )}

      {/* Mobile sticky bottom bar -- md altinda her zaman gorunur (count > 0 zaten yukarida guard'li) */}
      {!open && (
        <button
          ref={mobileTrigger}
          onClick={() => setOpen(true)}
          className="fixed bottom-[60px] left-0 right-0 md:hidden flex items-center gap-3 px-4 py-3 nv-glass"
          style={{
            zIndex: 45,
            borderTop: "1px solid var(--nv-accent-green)",
            boxShadow: "0 -4px 16px rgba(0,0,0,0.4)",
          }}
          aria-label={`Bahis sepetini aç (${count} tahmin)`}
        >
          <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="var(--nv-accent-green)" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <span
            className="nv-badge nv-badge-green flex-shrink-0"
          >
            {count} seçim
          </span>
          <div
            className="flex-1 text-center text-xs"
            style={{ color: "var(--nv-accent-green)" }}
          >
            Arşiv seçimleri
          </div>
          <span
            className="text-xs font-bold px-3 py-1.5 flex-shrink-0"
            style={{
              backgroundColor: "var(--nv-accent-green)",
              color: "var(--nv-text-inverse)",
              borderRadius: "var(--nv-radius-md)",
            }}
          >
            Aç
          </span>
        </button>
      )}

      {/* Acik panel -- desktop'ta sticky kart, mobile'da tam sheet */}
      {open && (
        <>
          <dialog
            ref={dialogRef}
            aria-label="Bahis Sepeti"
            onCancel={() => setOpen(false)}
            onClose={() => setOpen(false)}
            className="fixed z-50 m-0 top-auto w-full max-w-none flex flex-col md:left-auto md:right-4 md:bottom-4 md:w-80 md:max-h-[80vh] md:rounded-xl right-0 left-0 bottom-0 max-h-[85vh] rounded-t-2xl nv-glass backdrop:bg-black/60"
            style={{
              backgroundColor: "var(--nv-bg-glass)",
              border: "1px solid var(--nv-border-accent)",
              boxShadow: "var(--nv-shadow-lg)",
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 py-3"
              style={{ borderBottom: "1px solid var(--nv-border)" }}
            >
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5" fill="none" stroke="var(--nv-accent-green)" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <h3 className="text-sm font-bold" style={{ color: "var(--nv-accent-green)" }}>
                  Bahis Sepeti
                </h3>
                <span className="nv-badge nv-badge-green">
                  {count}
                </span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="w-7 h-7 rounded-full flex items-center justify-center transition-colors"
                style={{
                  color: "var(--nv-text-secondary)",
                  backgroundColor: "var(--nv-bg-elevated)",
                }}
                aria-label="Sepeti kapat"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Liste */}
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
              {items.map((it) => (
                <div
                  key={itemKey(it)}
                  className="nv-card flex items-start gap-2"
                  style={{
                    borderRadius: "var(--nv-radius-md)",
                    padding: "var(--nv-space-sm) var(--nv-space-md)",
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <PeriodBadge period={it.period} />
                      <span
                        className="text-[10px] truncate"
                        style={{ color: "var(--nv-text-tertiary)" }}
                      >
                        {it.homeTeam} - {it.awayTeam}
                      </span>
                    </div>
                    <div
                      className="text-[10px] uppercase truncate"
                      style={{
                        color: "var(--nv-text-tertiary)",
                        letterSpacing: "var(--nv-tracking-wide)",
                      }}
                    >
                      {it.marketLabel}
                    </div>
                    <div
                      className="text-sm font-semibold truncate"
                      style={{ color: "var(--nv-text-primary)" }}
                    >
                      {it.selectionLabel}
                    </div>
                  </div>
                  <div className="flex flex-col items-end flex-shrink-0 gap-1">
                    <span
                      className="text-sm font-bold"
                      style={{
                        fontFamily: "var(--nv-font-mono)",
                        color: "var(--nv-accent-green)",
                      }}
                    >
                      %{Math.round(it.pct)}
                    </span>
                    <button
                      onClick={() => removeItem(itemKey(it))}
                      className="w-5 h-5 rounded flex items-center justify-center transition-colors"
                      style={{
                        color: "var(--nv-text-tertiary)",
                        backgroundColor: "var(--nv-bg-elevated)",
                      }}
                      aria-label="Tahmini sepetten kaldır"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Footer */}
            <div
              className="px-4 py-3 space-y-2"
              style={{
                borderTop: "1px solid var(--nv-border)",
                backgroundColor: "var(--nv-bg-surface)",
              }}
            >
              <p
                className="text-xs"
                style={{ color: "var(--nv-text-tertiary)" }}
                role="status"
              >
                Yüzdeler geçmiş arşiv eşleşmelerinin sıklığıdır. Seçimlerin birlikte gerçekleşme olasılığı veya bahis oranı olarak kullanılamaz.
              </p>
              <button
                onClick={clear}
                className="w-full text-xs py-2 transition-colors font-semibold"
                style={{
                  backgroundColor: "var(--nv-accent-red-dim)",
                  color: "var(--nv-accent-red)",
                  border: "1px solid var(--nv-accent-red)",
                  borderRadius: "var(--nv-radius-md)",
                  transitionDuration: "var(--nv-duration-normal)",
                  transitionTimingFunction: "var(--nv-ease)",
                }}
              >
                Sepeti Temizle
              </button>
            </div>
          </dialog>
        </>
      )}
    </>
  );
}
