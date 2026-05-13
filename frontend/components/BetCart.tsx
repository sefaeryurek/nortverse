"use client";

import { useState } from "react";
import { useCart } from "@/lib/cart";

function PeriodBadge({ period }: { period: "ht" | "h2" | "ft" }) {
  const label = period === "ht" ? "İY" : period === "h2" ? "2Y" : "MS";
  return (
    <span
      className="text-[8px] font-bold px-1 rounded font-mono"
      style={{ backgroundColor: "#1e293b", color: "#94a3b8" }}
    >
      {label}
    </span>
  );
}

export default function BetCart() {
  const { items, hydrated, removeItem, clear, jointProb, estOdds, count } = useCart();
  const [open, setOpen] = useState(false);

  if (!hydrated || count === 0) {
    // Sepet boşsa hiçbir şey gösterme — UI kalabalığı azaltır
    return null;
  }

  const probPct = (jointProb * 100).toFixed(1);
  const odds = estOdds.toFixed(2);

  return (
    <>
      {/* Floating buton — sadece desktop (md+); mobile'de sticky bar ile değiştirildi */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-4 right-4 z-40 hidden md:flex items-center gap-2 px-4 py-3 rounded-full shadow-2xl transition-transform hover:scale-105"
          style={{
            backgroundColor: "#16a34a",
            color: "#ecfdf5",
            boxShadow: "0 8px 32px rgba(22,163,74,0.4)",
          }}
          aria-label={`Bahis sepetini aç (${count} tahmin)`}
        >
          <span className="text-lg">🧾</span>
          <span className="text-sm font-bold">Sepet</span>
          <span
            className="text-xs font-mono px-1.5 py-0.5 rounded-full"
            style={{ backgroundColor: "#052e16", color: "#bbf7d0" }}
          >
            {count}
          </span>
        </button>
      )}

      {/* Mobile sticky bottom bar — md altında her zaman görünür (count > 0 zaten yukarıda guard'lı) */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-0 left-0 right-0 md:hidden flex items-center gap-3 px-4 py-3 border-t shadow-2xl"
          style={{
            zIndex: 45,
            backgroundColor: "#0a1410",
            borderColor: "#15803d",
            boxShadow: "0 -4px 16px rgba(0,0,0,0.4)",
          }}
          aria-label={`Bahis sepetini aç (${count} tahmin)`}
        >
          <span className="text-lg">🧾</span>
          <span
            className="text-xs font-mono px-1.5 py-0.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: "#052e16", color: "#bbf7d0" }}
          >
            {count} leg
          </span>
          <div className="flex-1 flex items-center justify-center gap-3 text-xs font-mono" style={{ color: "#86efac" }}>
            <span>≈%{probPct}</span>
            <span style={{ color: "#475569" }}>·</span>
            <span>≈{odds}</span>
          </div>
          <span
            className="text-xs font-bold px-3 py-1.5 rounded-lg flex-shrink-0"
            style={{ backgroundColor: "#16a34a", color: "#ecfdf5" }}
          >
            Aç
          </span>
        </button>
      )}

      {/* Açık panel — desktop'ta sticky kart, mobile'da tam sheet */}
      {open && (
        <>
          {/* Mobile arkaplan */}
          <div
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-40 md:hidden"
            style={{ backgroundColor: "rgba(0,0,0,0.6)" }}
          />

          <div
            className="fixed z-50 flex flex-col md:right-4 md:bottom-4 md:w-80 md:max-h-[80vh] md:rounded-xl right-0 left-0 bottom-0 max-h-[85vh] rounded-t-2xl border"
            style={{
              backgroundColor: "#0a1410",
              borderColor: "#15803d",
              boxShadow: "0 16px 48px rgba(0,0,0,0.6)",
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 py-3 border-b"
              style={{ borderColor: "#1e293b" }}
            >
              <div className="flex items-center gap-2">
                <span className="text-base">🧾</span>
                <h3 className="text-sm font-bold" style={{ color: "#86efac" }}>
                  Bahis Sepeti
                </h3>
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  style={{ backgroundColor: "#0a1f17", color: "#4ade80" }}
                >
                  {count}
                </span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="w-7 h-7 rounded-full flex items-center justify-center transition-colors hover:bg-slate-800"
                style={{ color: "#94a3b8" }}
                aria-label="Sepeti kapat"
              >
                ✕
              </button>
            </div>

            {/* Liste */}
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2">
              {items.map((it, i) => (
                <div
                  key={`${it.matchId}-${it.marketKey}-${it.selectionLabel}-${it.period}-${i}`}
                  className="rounded-lg p-2 border flex items-start gap-2"
                  style={{ backgroundColor: "#0a0f17", borderColor: "#1e293b" }}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <PeriodBadge period={it.period} />
                      <span
                        className="text-[10px] truncate"
                        style={{ color: "#64748b" }}
                      >
                        {it.homeTeam} - {it.awayTeam}
                      </span>
                    </div>
                    <div className="text-[10px] uppercase tracking-wider truncate" style={{ color: "#475569" }}>
                      {it.marketLabel}
                    </div>
                    <div className="text-sm font-semibold truncate" style={{ color: "#cbd5e1" }}>
                      {it.selectionLabel}
                    </div>
                  </div>
                  <div className="flex flex-col items-end flex-shrink-0 gap-1">
                    <span className="text-sm font-bold font-mono" style={{ color: "#86efac" }}>
                      %{Math.round(it.pct)}
                    </span>
                    <button
                      onClick={() => removeItem(i)}
                      className="text-xs w-5 h-5 rounded flex items-center justify-center transition-colors hover:bg-slate-700"
                      style={{ color: "#64748b" }}
                      aria-label="Tahmini sepetten kaldır"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {/* Footer */}
            <div
              className="border-t px-4 py-3 space-y-2"
              style={{ borderColor: "#1e293b", backgroundColor: "#0a0f17" }}
            >
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-[10px] uppercase tracking-wider" style={{ color: "#475569" }}>
                    Toplam Olasılık
                  </div>
                  <div className="text-base font-bold font-mono" style={{ color: "#86efac" }}>
                    ≈%{probPct}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider" style={{ color: "#475569" }}>
                    Tahmini Oran
                  </div>
                  <div className="text-base font-bold font-mono" style={{ color: "#86efac" }}>
                    ≈{odds}
                  </div>
                </div>
              </div>

              <button
                onClick={clear}
                className="w-full text-xs py-2 rounded-lg transition-colors hover:bg-red-950"
                style={{
                  backgroundColor: "#1c0816",
                  color: "#fca5a5",
                  border: "1px solid #7f1d1d",
                }}
              >
                Sepeti Temizle
              </button>
            </div>
          </div>
        </>
      )}
    </>
  );
}
