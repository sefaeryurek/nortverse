import type { PatternResult } from "@/lib/types";

interface Props {
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  period: "ht" | "h2" | "ft";
}

// Yüzdeye göre renk
function pctColor(v: number) {
  if (v >= 60) return { color: "#4ade80", bg: "#052e16", border: "#166534" };
  if (v >= 40) return { color: "#fbbf24", bg: "#1c1400", border: "#92400e" };
  return { color: "#f87171", bg: "#1a0a0a", border: "#7f1d1d" };
}

interface OddCellProps {
  label: string;
  value: number;
  sub?: string;
}
function OddCell({ label, value, sub }: OddCellProps) {
  const pct = Math.round(value);
  const { color, bg, border } = pctColor(pct);
  return (
    <div
      className="flex flex-col items-center justify-center gap-0.5 p-2 rounded-lg border text-center"
      style={{ backgroundColor: bg, borderColor: border, minWidth: 0 }}
    >
      <span className="text-[10px] font-medium leading-tight" style={{ color: "#94a3b8" }}>
        {label}
      </span>
      {sub && (
        <span className="text-[9px] leading-tight" style={{ color: "#475569" }}>
          {sub}
        </span>
      )}
      <span className="text-base font-black font-mono mt-0.5" style={{ color }}>
        %{pct}
      </span>
    </div>
  );
}

interface SectionProps {
  title: string;
  children: React.ReactNode;
}
function Section({ title, children }: SectionProps) {
  return (
    <div className="space-y-2">
      <h4
        className="text-[11px] font-semibold uppercase tracking-widest"
        style={{ color: "#475569" }}
      >
        {title}
      </h4>
      {children}
    </div>
  );
}

function Row({ items }: { items: OddCellProps[] }) {
  return (
    <div
      className="grid gap-1.5"
      style={{ gridTemplateColumns: `repeat(${items.length}, 1fr)` }}
    >
      {items.map((item) => (
        <OddCell key={item.label + item.sub} {...item} />
      ))}
    </div>
  );
}

interface ScoreFreqProps {
  freq: Record<string, number>;
}
function ScoreFreq({ freq }: ScoreFreqProps) {
  const entries = Object.entries(freq).slice(0, 10);
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([score, count]) => (
        <span
          key={score}
          className="text-xs px-2 py-0.5 rounded font-mono"
          style={{ backgroundColor: "#1e293b", color: "#94a3b8" }}
        >
          <span style={{ color: "#e2e8f0", fontWeight: 600 }}>{score}</span>
          <span style={{ color: "#475569" }}> · {count}×</span>
        </span>
      ))}
    </div>
  );
}

function ArchiveCoupon({
  result,
  title,
  accentColor,
  period,
}: {
  result: PatternResult;
  title: string;
  accentColor: string;
  period: "ht" | "h2" | "ft";
}) {
  const showYariSonucu = period === "ft";

  return (
    <div
      className="rounded-xl p-4 border space-y-4"
      style={{ backgroundColor: "#0f1625", borderColor: "#1e293b" }}
    >
      {/* Başlık */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: accentColor }} />
          <h3 className="text-sm font-bold tracking-wide" style={{ color: accentColor }}>
            {title}
          </h3>
        </div>
        <span
          className="text-xs px-2 py-0.5 rounded-full font-mono"
          style={{ backgroundColor: "#1e293b", color: "#64748b" }}
        >
          {result.match_count} maç
        </span>
      </div>

      {/* Maç Sonucu */}
      <Section title="Maç Sonucu">
        <Row items={[
          { label: "MS 1", value: result.result_1_pct },
          { label: "MS X", value: result.result_x_pct },
          { label: "MS 2", value: result.result_2_pct },
        ]} />
        <Row items={[
          { label: "1X", sub: "Çifte Şans", value: result.dc_1x_pct },
          { label: "X2", sub: "Çifte Şans", value: result.dc_x2_pct },
          { label: "12", sub: "Çifte Şans", value: result.dc_12_pct },
        ]} />
      </Section>

      {/* Handikap */}
      <Section title="Handikaplı MS">
        <Row items={[
          { label: "1", sub: "Hnd (2:0)", value: result.hnd_h20_1_pct },
          { label: "X", sub: "Hnd (2:0)", value: result.hnd_h20_x_pct },
          { label: "2", sub: "Hnd (2:0)", value: result.hnd_h20_2_pct },
          { label: "1", sub: "Hnd (1:0)", value: result.hnd_h10_1_pct },
          { label: "X", sub: "Hnd (1:0)", value: result.hnd_h10_x_pct },
          { label: "2", sub: "Hnd (1:0)", value: result.hnd_h10_2_pct },
        ]} />
        <Row items={[
          { label: "1", sub: "Hnd (0:1)", value: result.hnd_a10_1_pct },
          { label: "X", sub: "Hnd (0:1)", value: result.hnd_a10_x_pct },
          { label: "2", sub: "Hnd (0:1)", value: result.hnd_a10_2_pct },
          { label: "1", sub: "Hnd (0:2)", value: result.hnd_a20_1_pct },
          { label: "X", sub: "Hnd (0:2)", value: result.hnd_a20_x_pct },
          { label: "2", sub: "Hnd (0:2)", value: result.hnd_a20_2_pct },
        ]} />
      </Section>

      {/* Alt/Üst + KG */}
      <Section title="Gol Sayısı ve KG">
        <Row items={[
          { label: "Alt 1.5", value: result.alt_15_pct },
          { label: "Üst 1.5", value: result.ust_15_pct },
          { label: "Alt 2.5", value: result.alt_25_pct },
          { label: "Üst 2.5", value: result.ust_25_pct },
          { label: "Alt 3.5", value: result.alt_35_pct },
          { label: "Üst 3.5", value: result.ust_35_pct },
        ]} />
        <Row items={[
          { label: "KG Var", value: result.kg_var_pct },
          { label: "KG Yok", value: result.kg_yok_pct },
        ]} />
      </Section>

      {/* MS + 1.5 Alt/Üst */}
      <Section title="MS Sonucu ve 1.5 Alt/Üst">
        <Row items={[
          { label: "1 + Alt", value: result.ms1_alt15_pct },
          { label: "1 + Üst", value: result.ms1_ust15_pct },
          { label: "X + Alt", value: result.msx_alt15_pct },
          { label: "X + Üst", value: result.msx_ust15_pct },
          { label: "2 + Alt", value: result.ms2_alt15_pct },
          { label: "2 + Üst", value: result.ms2_ust15_pct },
        ]} />
      </Section>

      {/* MS + KG */}
      <Section title="MS Sonucu ve Karşılıklı Gol">
        <Row items={[
          { label: "1 + Var", value: result.ms1_kg_var_pct },
          { label: "1 + Yok", value: result.ms1_kg_yok_pct },
          { label: "X + Var", value: result.msx_kg_var_pct },
          { label: "X + Yok", value: result.msx_kg_yok_pct },
          { label: "2 + Var", value: result.ms2_kg_var_pct },
          { label: "2 + Yok", value: result.ms2_kg_yok_pct },
        ]} />
      </Section>

      {/* Yarı Sonuçları (sadece FT/MS tabında) */}
      {showYariSonucu && (result.ht_result_1_pct > 0 || result.h2_result_1_pct > 0) && (
        <Section title="Yarı Sonuçları">
          {result.ht_result_1_pct > 0 && (
            <>
              <p className="text-[10px]" style={{ color: "#475569" }}>1. Yarı Sonucu</p>
              <Row items={[
                { label: "İY 1", value: result.ht_result_1_pct },
                { label: "İY X", value: result.ht_result_x_pct },
                { label: "İY 2", value: result.ht_result_2_pct },
                { label: "1X", sub: "İY Çifte", value: result.ht_dc_1x_pct },
                { label: "X2", sub: "İY Çifte", value: result.ht_dc_x2_pct },
                { label: "12", sub: "İY Çifte", value: result.ht_dc_12_pct },
              ]} />
              <Row items={[
                { label: "İY Alt 1.5", value: result.ht_alt_15_pct },
                { label: "İY Üst 1.5", value: result.ht_ust_15_pct },
                { label: "İY KG Var", value: result.ht_kg_var_pct },
                { label: "İY KG Yok", value: result.ht_kg_yok_pct },
              ]} />
            </>
          )}
          {result.h2_result_1_pct > 0 && (
            <>
              <p className="text-[10px] mt-2" style={{ color: "#475569" }}>2. Yarı Sonucu</p>
              <Row items={[
                { label: "2Y 1", value: result.h2_result_1_pct },
                { label: "2Y X", value: result.h2_result_x_pct },
                { label: "2Y 2", value: result.h2_result_2_pct },
              ]} />
            </>
          )}
        </Section>
      )}

      {/* Skor Sıklığı */}
      {Object.keys(result.score_freq).length > 0 && (
        <Section title="Skor Sıklığı">
          <ScoreFreq freq={result.score_freq} />
        </Section>
      )}
    </div>
  );
}

export default function IddaaCoupon({ patternB, patternC, period }: Props) {
  const hasB = patternB !== null && patternB.match_count >= 5;
  const hasC = patternC !== null && patternC.match_count >= 5;

  if (!hasB && !hasC) {
    return (
      <div
        className="rounded-xl p-8 border text-center"
        style={{ backgroundColor: "#0f1625", borderColor: "#1e293b" }}
      >
        <div className="text-3xl mb-3">📊</div>
        <p className="text-sm font-medium" style={{ color: "#64748b" }}>
          Bu periyot için yeterli arşiv verisi bulunamadı.
        </p>
        <p className="text-xs mt-1" style={{ color: "#374151" }}>
          Minimum 5 eşleşme gerekiyor
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
      {hasB ? (
        <ArchiveCoupon
          result={patternB!}
          title="Arşiv 1 — Skor Seti"
          accentColor="#4ade80"
          period={period}
        />
      ) : (
        <div
          className="rounded-xl p-6 border flex items-center justify-center"
          style={{ backgroundColor: "#0f1625", borderColor: "#1e293b" }}
        >
          <p className="text-sm" style={{ color: "#374151" }}>
            Arşiv 1: Yeterli veri yok
          </p>
        </div>
      )}
      {hasC ? (
        <ArchiveCoupon
          result={patternC!}
          title="Arşiv 2 — Oran Benzerliği"
          accentColor="#c084fc"
          period={period}
        />
      ) : (
        <div
          className="rounded-xl p-6 border flex items-center justify-center"
          style={{ backgroundColor: "#0f1625", borderColor: "#1e293b" }}
        >
          <p className="text-sm" style={{ color: "#374151" }}>
            Arşiv 2: Yeterli veri yok
          </p>
        </div>
      )}
    </div>
  );
}
