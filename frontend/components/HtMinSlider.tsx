"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * İY panosu asgari olasılık kaydırıcısı (Sprint 94 K-2). Değer sürüklerken ekranda değişir, bırakınca adres
 * güncellenir (her adımda sunucuya gidilmez). `baseHref` diğer süzgeçleri taşır, `min` içermez.
 */
export default function HtMinSlider({ value, baseHref, label }: { value: number; baseHref: string; label: string }) {
  const router = useRouter();
  const [current, setCurrent] = useState(value);
  const commit = (v: number) => {
    if (v === value) return;
    router.replace(v > 0 ? `${baseHref}&min=${v}` : baseHref, { scroll: false });
  };
  return (
    <label className="flex items-center gap-2" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>
      <span className="whitespace-nowrap">{label.replace("{pct}", String(current))}</span>
      <input
        type="range" min={0} max={90} step={5} value={current}
        onChange={(e) => setCurrent(Number(e.target.value))}
        onPointerUp={(e) => commit(Number((e.target as HTMLInputElement).value))}
        onKeyUp={(e) => commit(Number((e.target as HTMLInputElement).value))}
        className="w-32 accent-[var(--nv-accent-green)]"
      />
    </label>
  );
}
