import type { PatternResult, PeriodOut } from "@/lib/types";
import ScoreList from "./ScoreList";

interface Props {
  period: PeriodOut;
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  label: string;
}

interface OddItem {
  label: string;
  value: number;
}

function OddCell({ label, value }: OddItem) {
  const pct = Math.round(value);
  const bg =
    pct >= 60 ? "#052e16" : pct >= 40 ? "#1c1400" : "#1a0a0a";
  const color =
    pct >= 60 ? "#4ade80" : pct >= 40 ? "#fbbf24" : "#f87171";
  const border =
    pct >= 60 ? "#166534" : pct >= 40 ? "#92400e" : "#7f1d1d";

  return (
    <div className="flex flex-col items-center gap-1 p-2 rounded-lg border" style={{ backgroundColor: bg, borderColor: border }}>
      <span className="text-[11px] font-medium" style={{ color: "#94a3b8" }}>
        {label}
      </span>
      <span className="text-lg font-black font-mono" style={{ color }}>
        %{pct}
      </span>
    </div>
  );
}

function PatternCoupon({ result, title }: { result: PatternResult; title: string }) {
  const kg_yok = 100 - result.kg_var_pct;
  const alt_25 = 100 - result.over_25_pct;

  const rows: OddItem[][] = [
    [
      { label: "MS1", value: result.result_1_pct },
      { label: "MSX", value: result.result_x_pct },
      { label: "MS2", value: result.result_2_pct },
    ],
    [
      { label: "KG Var", value: result.kg_var_pct },
      { label: "KG Yok", value: kg_yok },
      { label: "2.5 Üst", value: result.over_25_pct },
      { label: "2.5 Alt", value: alt_25 },
    ],
  ];

  return (
    <div
      className="rounded-xl p-4 border space-y-4"
      style={{ backgroundColor: "#0f1625", borderColor: "#2d3748" }}
    >
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: "#3b82f6" }} />
        <h3 className="text-sm font-bold tracking-wide uppercase" style={{ color: "#93c5fd" }}>
          {title}
        </h3>
      </div>

      {rows.map((row, i) => (
        <div key={i} className={`grid gap-2`} style={{ gridTemplateColumns: `repeat(${row.length}, 1fr)` }}>
          {row.map((item) => (
            <OddCell key={item.label} {...item} />
          ))}
        </div>
      ))}
    </div>
  );
}

export default function IddaaCoupon({ period, patternB, patternC, label }: Props) {
  const hasScores =
    period.scores_1.length + period.scores_x.length + period.scores_2.length > 0;

  const hasB = patternB !== null && patternB.match_count >= 5;
  const hasC = patternC !== null && patternC.match_count >= 5;

  return (
    <div className="space-y-4">
      {/* Tahmin kuponları */}
      {!hasB && !hasC ? (
        <div
          className="rounded-xl p-6 border text-center"
          style={{ backgroundColor: "#0f1625", borderColor: "#2d3748" }}
        >
          <p className="text-sm" style={{ color: "#64748b" }}>
            Bu periyot için yeterli arşiv verisi yok.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {hasB ? (
            <PatternCoupon result={patternB!} title="Tahmin — Arşiv 1" />
          ) : (
            <div
              className="rounded-xl p-4 border flex items-center justify-center"
              style={{ backgroundColor: "#0f1625", borderColor: "#2d3748" }}
            >
              <p className="text-xs" style={{ color: "#475569" }}>
                Arşiv-1: Yeterli veri yok
              </p>
            </div>
          )}
          {hasC ? (
            <PatternCoupon result={patternC!} title="Tahmin — Arşiv 2" />
          ) : (
            <div
              className="rounded-xl p-4 border flex items-center justify-center"
              style={{ backgroundColor: "#0f1625", borderColor: "#2d3748" }}
            >
              <p className="text-xs" style={{ color: "#475569" }}>
                Arşiv-2: Yeterli veri yok
              </p>
            </div>
          )}
        </div>
      )}

      {/* 3.5+ Skorlar */}
      {hasScores && (
        <div
          className="rounded-xl p-4 border"
          style={{ backgroundColor: "#0f1625", borderColor: "#2d3748" }}
        >
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: "#64748b" }}>
            {label} — 3.5+ Skor Listesi
          </h3>
          <div className="flex flex-col gap-3 sm:flex-row">
            <ScoreList scores={period.scores_1} type="1" label="MS1" />
            <ScoreList scores={period.scores_x} type="x" label="MSX" />
            <ScoreList scores={period.scores_2} type="2" label="MS2" />
          </div>
        </div>
      )}
    </div>
  );
}
