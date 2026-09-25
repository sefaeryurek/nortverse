import type { AnalysisEvidence, AnalysisValidation } from "@/lib/types";

interface Props {
  evidenceData: AnalysisEvidence | null;
  validationData: AnalysisValidation | null;
}

export default function ValidationSection({ evidenceData, validationData }: Props) {
  if (!evidenceData && !validationData) return null;

  return (
    <section
      className="nv-card nv-fade-in text-xs"
      style={{
        borderRadius: "var(--nv-radius-lg)",
        padding: "var(--nv-space-lg)",
        color: "var(--nv-text-secondary)",
      }}
      aria-label="Analiz doğrulama kapsamı"
    >
      <h2 className="text-sm font-semibold" style={{ color: "var(--nv-text-primary)" }}>Analiz doğrulama kapsamı</h2>
      {evidenceData && (<>
        <p className="mt-1 leading-relaxed" style={{ color: "var(--nv-text-tertiary)" }}>
          Yalnızca analiz ve arşiv desenleri maçtan önce kaydedilmiş, sonucu bilinen maçlar sayılır.
        </p>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {[
            ["Maç öncesi", evidenceData.eligible_matches],
            ["Arşiv 1", evidenceData.archive_1_evaluated],
            ["Arşiv 2", evidenceData.archive_2_evaluated],
          ].map(([label, count]) => (
            <div
              key={label}
              className="nv-card px-2 py-2 text-center"
              style={{ borderRadius: "var(--nv-radius-md)" }}
            >
              <div
                className="text-lg font-bold"
                style={{
                  fontFamily: "var(--nv-font-mono)",
                  color: "var(--nv-text-primary)",
                }}
              >
                {count}
              </div>
              <div className="text-[10px]" style={{ color: "var(--nv-text-tertiary)" }}>{label}</div>
            </div>
          ))}
        </div>
        <p className="mt-3 leading-relaxed" style={{ color: "var(--nv-text-tertiary)" }}>
          Her arşiv için {evidenceData.minimum_for_rate} sonuçlu maç tamamlanmadan isabet oranı sunulmuyor.
          Ekrandaki yüzdeler geçmiş eşleşme sıklığıdır.
        </p>
        <p className="mt-2 leading-relaxed" style={{ color: "var(--nv-text-secondary)" }}>
          Maç sonu skor listesi: {evidenceData.score_list_hits}/{evidenceData.score_list_evaluated} maçta
          gerçek skor seçilen listede bulundu.
          {evidenceData.score_list_evaluated < evidenceData.minimum_for_rate
            ? " Örneklem henüz sonuç çıkarmak için küçük."
            : ` Skor kapsama oranı: %${Math.round(100 * evidenceData.score_list_hits / evidenceData.score_list_evaluated)}. Bu oran bahis getirisi veya olasılık kalibrasyonu değildir.`}
        </p>
        <p className="mt-2 leading-relaxed" style={{ color: "var(--nv-accent-amber)" }}>
          Skor listesinin basit bir yaygın skor seçimini geçtiği henüz gösterilmedi. Bu liste doğrulanmış bahis önerisi değildir.
        </p>
      </>)}
      {validationData && (
        <div className="mt-4 pt-3" style={{ borderTop: "1px solid var(--nv-border)" }}>
          <h3 className="font-semibold" style={{ color: "var(--nv-text-primary)" }}>İleri dönem seçim takibi</h3>
          <p className="mt-1 leading-relaxed" style={{ color: "var(--nv-text-tertiary)" }}>
            Toplam {validationData.total_snapshots} snapshot sabitlendi.
            Kurallar: {validationData.rule_version} -- Temel: {validationData.baseline_version}.
          </p>
          {validationData.markets.length === 0 ? (
            <p className="mt-2" style={{ color: "var(--nv-text-tertiary)" }}>Henüz pazar verisi yok.</p>
          ) : (
            <div className="mt-3 space-y-4">
              {validationData.markets.map((m) => {
                const mLabel = { result: "Maç sonucu", over_25: "2.5 Alt/Üst", btts: "Karşılıklı gol" }[m.market];
                const tierBadge = m.display_tier === "cok_erken"
                  ? <span className="nv-badge nv-badge-amber ml-2">Çok Erken</span>
                  : m.display_tier === "on_bulgu"
                  ? <span className="nv-badge nv-badge-amber ml-2">Ön Bulgu</span>
                  : <span className="nv-badge nv-badge-green ml-2">Tam</span>;
                const pct = (v: number | null) => v !== null ? `%${(v * 100).toFixed(1)}` : "---";
                const ci = (lo: number | null, hi: number | null) =>
                  lo !== null && hi !== null ? `(${pct(lo)} -- ${pct(hi)})` : "";
                return (
                  <div
                    key={m.market}
                    className="nv-card"
                    style={{
                      borderRadius: "var(--nv-radius-md)",
                      padding: "var(--nv-space-md)",
                    }}
                  >
                    <div className="flex items-center">
                      <span className="font-semibold" style={{ color: "var(--nv-text-primary)" }}>{mLabel}</span>
                      {tierBadge}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1" style={{ color: "var(--nv-text-secondary)" }}>
                      <span>Fırsat: {m.opportunities}</span>
                      <span>Seçim: {m.issued}</span>
                      <span>Kaçınma: {m.abstained}</span>
                      <span>Çözülen: {m.resolved_issued}</span>
                    </div>
                    {m.display_tier !== "cok_erken" && (
                      <>
                        <div className="mt-2 space-y-1" style={{ color: "var(--nv-text-secondary)" }}>
                          <div>Kapsam: {pct(m.coverage)} {ci(m.coverage_ci_low, m.coverage_ci_high)}</div>
                          <div>Model isabet: {pct(m.model_hit_rate)} {ci(m.model_hit_rate_ci_low, m.model_hit_rate_ci_high)}</div>
                          <div>Temel isabet: {pct(m.baseline_hit_rate)} {ci(m.baseline_hit_rate_ci_low, m.baseline_hit_rate_ci_high)}</div>
                          {m.paired_difference !== null && (
                            <div>Fark: {(m.paired_difference * 100).toFixed(1)} puan</div>
                          )}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1" style={{ color: "var(--nv-text-tertiary)" }}>
                          <span>İkisi de ok: {m.both_hit}</span>
                          <span>Sadece model: {m.model_only}</span>
                          <span>Sadece temel: {m.baseline_only}</span>
                          <span>İkisi de x: {m.neither}</span>
                        </div>
                      </>
                    )}
                    {m.display_tier === "tam" && (
                      <div className="mt-2 space-y-1" style={{ color: "var(--nv-text-tertiary)" }}>
                        <div>Yayımlanan sıklık ort.: %{m.avg_published_frequency?.toFixed(1) ?? "---"}</div>
                        <div>Gözlenen isabet: %{m.observed_hit_rate?.toFixed(1) ?? "---"}</div>
                        <div>Kalibrasyon farkı: {m.calibration_gap?.toFixed(1) ?? "---"} puan</div>
                        <div>Brier (seçilen olay): {m.selected_event_brier?.toFixed(4) ?? "---"}</div>
                      </div>
                    )}
                    {m.display_tier === "cok_erken" && (
                      <p className="mt-2" style={{ color: "var(--nv-accent-amber)", opacity: 0.8 }}>Sonuç çıkarmak için çok erken.</p>
                    )}
                    {m.display_tier === "on_bulgu" && (
                      <p className="mt-2" style={{ color: "var(--nv-accent-amber)", opacity: 0.8 }}>Ön bulgu — sonuçlar değişebilir.</p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          <div className="mt-3 space-y-1" style={{ color: "var(--nv-text-tertiary)" }}>
            <p>Arşiv yüzdesi kalibre olasılık değildir.</p>
            <p>Oran verisi olmadan ROI veya karlılık ölçülemez.</p>
            {validationData.markets.some((m) => m.display_tier === "tam" && m.market === "result") && (
              <p>{validationData.brier_note}</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
