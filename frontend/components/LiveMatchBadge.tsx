"use client";

import { useEffect, useState } from "react";
import { isLiveScoreStale } from "@/lib/score-freshness";

interface Props {
  home: number;
  away: number;
  minute: string | null;
  checkedAt: string | null;
  checkedLabel: string | null;
  initialStale: boolean;
}

export default function LiveMatchBadge({ home, away, minute, checkedAt, checkedLabel, initialStale }: Props) {
  const [stale, setStale] = useState(initialStale);

  useEffect(() => {
    const update = () => setStale(isLiveScoreStale(checkedAt));
    update();
    const timer = window.setInterval(update, 15_000);
    return () => window.clearInterval(timer);
  }, [checkedAt]);

  const minuteLabel = minute === "HT" ? "İY" : minute ? `${minute}′` : "CANLI";
  return (
    <span
      aria-label={stale ? "Son görülen skor; güncel veri bekleniyor" : "Canlı skor"}
      data-stale={stale}
      className={`flex-shrink-0 rounded px-2 py-1 text-xs font-semibold ${stale
        ? "bg-amber-950 text-amber-200" : "bg-green-950 text-green-300"}`}
    >
      <span>{stale ? "Son skor" : minuteLabel}</span>{" "}
      <span className="font-mono text-sm font-bold">{home} - {away}</span>
      <span className="block text-[10px] font-normal opacity-75">
        {checkedLabel ? `Son kontrol ${checkedLabel}` : "Kontrol zamanı bilinmiyor"}
      </span>
    </span>
  );
}
