"use client";

import { useEffect, useState } from "react";
import { isLiveScoreStale } from "@/lib/score-freshness";
import { useLocale } from "@/lib/locale-context";

interface Props {
  home: number;
  away: number;
  minute: string | null;
  checkedAt: string | null;
  checkedLabel: string | null;
  initialStale: boolean;
}

export default function LiveMatchBadge({ home, away, minute, checkedAt, checkedLabel, initialStale }: Props) {
  const { t } = useLocale();
  const [stale, setStale] = useState(initialStale);

  useEffect(() => {
    const update = () => setStale(isLiveScoreStale(checkedAt));
    update();
    const timer = window.setInterval(update, 15_000);
    return () => window.clearInterval(timer);
  }, [checkedAt]);

  const minuteLabel = minute === "HT" ? t.liveMatchBadge.ht : minute ? `${minute}′` : t.liveMatchBadge.live;

  return (
    <span
      aria-label={stale ? t.liveMatchBadge.staleScore : t.liveMatchBadge.liveScore}
      data-stale={stale}
      className={stale ? "nv-badge nv-badge-amber" : "nv-badge nv-badge-red nv-live-pulse"}
      style={{
        flexShrink: 0,
        padding: "4px 10px",
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 2,
      }}
    >
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        {!stale && (
          <span
            className="nv-live-pulse"
            style={{
              width: 6,
              height: 6,
              borderRadius: "var(--nv-radius-full)",
              backgroundColor: "var(--nv-live)",
              boxShadow: `0 0 6px var(--nv-live-glow)`,
            }}
          />
        )}
        <span>{stale ? t.liveMatchBadge.lastScore : minuteLabel}</span>
      </span>
      <span
        style={{
          fontFamily: "var(--nv-font-mono)",
          fontSize: "var(--nv-text-sm)",
          fontWeight: 700,
        }}
      >
        {home} - {away}
      </span>
      <span
        style={{
          fontSize: "var(--nv-text-2xs)",
          fontWeight: 400,
          opacity: 0.75,
        }}
      >
        {checkedLabel ? t.liveMatchBadge.lastCheck.replace("{time}", checkedLabel) : t.liveMatchBadge.unknownCheck}
      </span>
    </span>
  );
}
