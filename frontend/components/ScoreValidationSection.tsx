import type { ScoreValidation } from "@/lib/types";

interface Props {
  scoreValidation: ScoreValidation | null;
}

export default function ScoreValidationSection({ scoreValidation }: Props) {
  if (!scoreValidation) return null;

  return (
    <section
      className="nv-card nv-fade-in text-xs"
      style={{
        borderRadius: "var(--nv-radius-lg)",
        padding: "var(--nv-space-lg)",
        color: "var(--nv-text-secondary)",
      }}
      aria-label="İleri dönem skor karşılaştırması"
    >
      <h2 className="text-sm font-semibold" style={{ color: "var(--nv-text-primary)" }}>İleri dönem skor karşılaştırması</h2>
      <p className="mt-1 leading-relaxed" style={{ color: "var(--nv-text-tertiary)" }}>
        Maç öncesi {scoreValidation.recorded} skor listesi sabitlendi; {scoreValidation.resolved} maçın kesin sonucu doğrulandı.
        {" "}{scoreValidation.paired} maçta aynı uzunlukta geçmişte en sık görülen skor listesiyle karşılaştırma yapılabildi.
      </p>
      {scoreValidation.paired > 0 && (
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1" style={{ color: "var(--nv-text-primary)" }}>
          <span>Analiz listesi: {scoreValidation.paired_model_hits}/{scoreValidation.paired}</span>
          <span>Basit liste: {scoreValidation.baseline_hits}/{scoreValidation.paired}</span>
          <span>İkisi de: {scoreValidation.both_hit}</span>
          <span>Sadece analiz: {scoreValidation.model_only}</span>
          <span>Sadece basit: {scoreValidation.baseline_only}</span>
          <span>İkisi de değil: {scoreValidation.neither}</span>
        </div>
      )}
      <p className="mt-2" style={{ color: "var(--nv-text-tertiary)" }}>
        {scoreValidation.paired < scoreValidation.minimum_for_rate
          ? `${scoreValidation.minimum_for_rate} eşleşmiş sonuçtan önce oran gösterilmez.`
          : `Analiz listesi %${Math.round(100 * scoreValidation.paired_model_hits / scoreValidation.paired)}, basit liste %${Math.round(100 * scoreValidation.baseline_hits / scoreValidation.paired)} kapsam sağladı. Fark %95 aralığı: ${scoreValidation.difference_ci_low_pp} ile ${scoreValidation.difference_ci_high_pp} puan.`}
        {" "}Skor kapsamı bahis getirisi veya olasılık kalibrasyonu değildir.
      </p>
    </section>
  );
}
