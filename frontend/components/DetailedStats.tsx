"use client";

import { useEffect, useState } from "react";
import type { PatternResult } from "@/lib/types";
import { type Period, periodLabels } from "@/lib/labels";

interface Props {
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  period: Period;
}

const STORAGE_KEY = "nortverse_detailed_open";

// Yeni profesyonel renk skalası: yeşil = güçlü, gri/silik = zayıf.
// Eski mavi/turuncu/kırmızı yerine sade tonlama.
function pctStyle(pct: number) {
  if (pct >= 75) return { color: "#86efac", bg: "#062618", border: "#15803d", opacity: 1 };
  if (pct >= 60) return { color: "#cbd5e1", bg: "#0a1410", border: "#1e3a2c", opacity: 1 };
  if (pct >= 50) return { color: "#94a3b8", bg: "#0f172a", border: "#1e293b", opacity: 0.95 };
  if (pct >= 40) return { color: "#64748b", bg: "#0a0d14", border: "#1e293b", opacity: 0.7 };
  return { color: "#475569", bg: "#0a0d14", border: "#1e293b", opacity: 0.45 };
}

interface OddCellProps {
  label: string;
  value: number;
  sub?: string;
}
function OddCell({ label, value, sub }: OddCellProps) {
  const pct = Math.round(value);
  const s = pctStyle(pct);
  return (
    <div
      className="flex flex-col items-center justify-center gap-px px-1 py-1.5 rounded border text-center"
      style={{ backgroundColor: s.bg, borderColor: s.border, minWidth: 0, opacity: s.opacity }}
    >
      <span className="text-[9px] font-medium leading-tight" style={{ color: "#64748b" }}>
        {label}
      </span>
      {sub && (
        <span className="text-[8px] leading-tight" style={{ color: "#374151" }}>
          {sub}
        </span>
      )}
      <span className="text-sm font-extrabold font-mono leading-none" style={{ color: s.color }}>
        %{pct}
      </span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "#475569" }}>
        {title}
      </h4>
      {children}
    </div>
  );
}

function Row({ items }: { items: OddCellProps[] }) {
  return (
    <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${items.length}, 1fr)` }}>
      {items.map((item) => (
        <OddCell key={item.label + (item.sub ?? "")} {...item} />
      ))}
    </div>
  );
}

function SubLabel({ text }: { text: string }) {
  return <p className="text-[9px] mt-1" style={{ color: "#374151" }}>{text}</p>;
}

function ScoreFreq({ freq }: { freq: Record<string, number> | null | undefined }) {
  if (!freq) return null;
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

function ArchiveDetailCard({
  result,
  title,
  accentColor,
  period,
}: {
  result: PatternResult;
  title: string;
  accentColor: string;
  period: Period;
}) {
  const isFT = period === "ft";
  const lbl = periodLabels(period);

  return (
    <div className="rounded-xl p-3 border space-y-3" style={{ backgroundColor: "#0a0d14", borderColor: "#1e293b" }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: accentColor }} />
          <h3 className="text-sm font-bold tracking-wide" style={{ color: accentColor }}>{title}</h3>
        </div>
        <span
          className="text-xs px-2 py-0.5 rounded-full font-mono"
          style={{ backgroundColor: "#1e293b", color: "#64748b" }}
        >
          {result.match_count} maç
        </span>
      </div>

      <Section title={lbl.sonuc}>
        <Row items={[
          { label: `${lbl.prefix} 1`, value: result.result_1_pct },
          { label: `${lbl.prefix} X`, value: result.result_x_pct },
          { label: `${lbl.prefix} 2`, value: result.result_2_pct },
        ]} />
        <Row items={[
          { label: "1X", sub: "Çifte Şans", value: result.dc_1x_pct },
          { label: "X2", sub: "Çifte Şans", value: result.dc_x2_pct },
          { label: "12", sub: "Çifte Şans", value: result.dc_12_pct },
        ]} />
      </Section>

      {isFT && result.iy_ms_xx_pct > 0 && (
        <Section title="İlk Yarı / Maç Sonucu">
          <Row items={[
            { label: "1/1", value: result.iy_ms_11_pct },
            { label: "1/X", value: result.iy_ms_1x_pct },
            { label: "1/2", value: result.iy_ms_12_pct },
          ]} />
          <Row items={[
            { label: "X/1", value: result.iy_ms_x1_pct },
            { label: "X/X", value: result.iy_ms_xx_pct },
            { label: "X/2", value: result.iy_ms_x2_pct },
          ]} />
          <Row items={[
            { label: "2/1", value: result.iy_ms_21_pct },
            { label: "2/X", value: result.iy_ms_2x_pct },
            { label: "2/2", value: result.iy_ms_22_pct },
          ]} />
        </Section>
      )}

      {/* MS + 2.5 — sadece FT (IY/2Y'de iddaa 2.5 hattı açmaz) */}
      {isFT && (
        <Section title={lbl.combo25}>
          <Row items={[
            { label: "1 + Alt", value: result.ms1_alt25_pct },
            { label: "1 + Üst", value: result.ms1_ust25_pct },
            { label: "X + Alt", value: result.msx_alt25_pct },
            { label: "X + Üst", value: result.msx_ust25_pct },
            { label: "2 + Alt", value: result.ms2_alt25_pct },
            { label: "2 + Üst", value: result.ms2_ust25_pct },
          ]} />
        </Section>
      )}

      <Section title={lbl.fark}>
        <Row items={[
          { label: "Ev 1 fark", value: result.fark_ev1_pct },
          { label: "Ev 2 fark", value: result.fark_ev2_pct },
          { label: "Ev 3+", value: result.fark_ev3p_pct },
          { label: "Berabere", value: result.fark_ber_pct },
        ]} />
        <Row items={[
          { label: "Dep 1 fark", value: result.fark_dep1_pct },
          { label: "Dep 2 fark", value: result.fark_dep2_pct },
          { label: "Dep 3+", value: result.fark_dep3p_pct },
        ]} />
      </Section>

      {/* Handikap — sadece FT (IY/2Y'de iddaa handikap açmaz) */}
      {isFT && (
        <Section title={lbl.hnd}>
          <Row items={[
            { label: "1", sub: "Hnd (2:0)", value: result.hnd_a20_1_pct },
            { label: "X", sub: "Hnd (2:0)", value: result.hnd_a20_x_pct },
            { label: "2", sub: "Hnd (2:0)", value: result.hnd_a20_2_pct },
            { label: "1", sub: "Hnd (1:0)", value: result.hnd_a10_1_pct },
            { label: "X", sub: "Hnd (1:0)", value: result.hnd_a10_x_pct },
            { label: "2", sub: "Hnd (1:0)", value: result.hnd_a10_2_pct },
          ]} />
          <Row items={[
            { label: "1", sub: "Hnd (0:1)", value: result.hnd_h10_1_pct },
            { label: "X", sub: "Hnd (0:1)", value: result.hnd_h10_x_pct },
            { label: "2", sub: "Hnd (0:1)", value: result.hnd_h10_2_pct },
            { label: "1", sub: "Hnd (0:2)", value: result.hnd_h20_1_pct },
            { label: "X", sub: "Hnd (0:2)", value: result.hnd_h20_x_pct },
            { label: "2", sub: "Hnd (0:2)", value: result.hnd_h20_2_pct },
          ]} />
        </Section>
      )}

      <Section title={lbl.taraf}>
        <SubLabel text="Ev Sahibi" />
        {/* IY/2Y'de 2.5 hattı açılmaz (Alt %99+, Üst nadir) → sadece FT'de göster */}
        <Row items={
          isFT
            ? [
                { label: "Alt 0.5", sub: "Ev", value: result.ev_alt_05_pct },
                { label: "Üst 0.5", sub: "Ev", value: result.ev_ust_05_pct },
                { label: "Alt 1.5", sub: "Ev", value: result.ev_alt_15_pct },
                { label: "Üst 1.5", sub: "Ev", value: result.ev_ust_15_pct },
                { label: "Alt 2.5", sub: "Ev", value: result.ev_alt_25_pct },
                { label: "Üst 2.5", sub: "Ev", value: result.ev_ust_25_pct },
              ]
            : [
                { label: "Alt 0.5", sub: "Ev", value: result.ev_alt_05_pct },
                { label: "Üst 0.5", sub: "Ev", value: result.ev_ust_05_pct },
                { label: "Alt 1.5", sub: "Ev", value: result.ev_alt_15_pct },
                { label: "Üst 1.5", sub: "Ev", value: result.ev_ust_15_pct },
              ]
        } />
        <SubLabel text="Deplasman" />
        <Row items={
          isFT
            ? [
                { label: "Alt 0.5", sub: "Dep", value: result.dep_alt_05_pct },
                { label: "Üst 0.5", sub: "Dep", value: result.dep_ust_05_pct },
                { label: "Alt 1.5", sub: "Dep", value: result.dep_alt_15_pct },
                { label: "Üst 1.5", sub: "Dep", value: result.dep_ust_15_pct },
                { label: "Alt 2.5", sub: "Dep", value: result.dep_alt_25_pct },
                { label: "Üst 2.5", sub: "Dep", value: result.dep_ust_25_pct },
              ]
            : [
                { label: "Alt 0.5", sub: "Dep", value: result.dep_alt_05_pct },
                { label: "Üst 0.5", sub: "Dep", value: result.dep_ust_05_pct },
                { label: "Alt 1.5", sub: "Dep", value: result.dep_alt_15_pct },
                { label: "Üst 1.5", sub: "Dep", value: result.dep_ust_15_pct },
              ]
        } />
        {isFT && result.ev_ht_ust_05_pct > 0 && (
          <>
            <SubLabel text="1. Yarı" />
            <Row items={[
              { label: "Ev 1.Y Alt", sub: "0.5", value: result.ev_ht_alt_05_pct },
              { label: "Ev 1.Y Üst", sub: "0.5", value: result.ev_ht_ust_05_pct },
              { label: "Dep 1.Y Alt", sub: "0.5", value: result.dep_ht_alt_05_pct },
              { label: "Dep 1.Y Üst", sub: "0.5", value: result.dep_ht_ust_05_pct },
            ]} />
          </>
        )}
      </Section>

      <Section title={lbl.toplamGol}>
        <SubLabel text="Gol Aralığı" />
        <Row items={[
          { label: "0-1 Gol", value: result.gol_01_pct },
          { label: "2-3 Gol", value: result.gol_23_pct },
          { label: "4-5 Gol", value: result.gol_45_pct },
          { label: "6+ Gol", value: result.gol_6p_pct },
        ]} />
        {isFT && result.encok_gol_1y_pct > 0 && (
          <>
            <SubLabel text="En Çok Gol Olacak Yarı" />
            <Row items={[
              { label: "1. Yarı", value: result.encok_gol_1y_pct },
              { label: "Eşit", value: result.encok_gol_esit_pct },
              { label: "2. Yarı", value: result.encok_gol_2y_pct },
            ]} />
          </>
        )}
      </Section>

      {isFT && result.iy_ust_05_pct > 0 && (
        <Section title="Yarı Alt/Üst">
          <SubLabel text="1. Yarı" />
          <Row items={[
            { label: "Alt 0.5", sub: "1Y", value: result.iy_alt_05_pct },
            { label: "Üst 0.5", sub: "1Y", value: result.iy_ust_05_pct },
            { label: "Alt 1.5", sub: "1Y", value: result.iy_alt_15_pct },
            { label: "Üst 1.5", sub: "1Y", value: result.iy_ust_15_pct },
            { label: "Alt 2.5", sub: "1Y", value: result.iy_alt_25_pct },
            { label: "Üst 2.5", sub: "1Y", value: result.iy_ust_25_pct },
          ]} />
          <Row items={[
            { label: "İki Yarı Alt", sub: "1.5", value: result.iki_yari_alt15_pct },
            { label: "İki Yarı Üst", sub: "1.5", value: result.iki_yari_ust15_pct },
          ]} />
        </Section>
      )}

      <Section title="Gol Sayısı ve KG">
        {/* IY/2Y'de 2.5 ve 3.5 hatları açılmaz → sadece FT'de göster */}
        <Row items={
          isFT
            ? [
                { label: "Alt 1.5", value: result.alt_15_pct },
                { label: "Üst 1.5", value: result.ust_15_pct },
                { label: "Alt 2.5", value: result.alt_25_pct },
                { label: "Üst 2.5", value: result.ust_25_pct },
                { label: "Alt 3.5", value: result.alt_35_pct },
                { label: "Üst 3.5", value: result.ust_35_pct },
              ]
            : [
                { label: "Alt 1.5", value: result.alt_15_pct },
                { label: "Üst 1.5", value: result.ust_15_pct },
              ]
        } />
        <Row items={[
          { label: "KG Var", value: result.kg_var_pct },
          { label: "KG Yok", value: result.kg_yok_pct },
        ]} />
      </Section>

      <Section title={lbl.combo15}>
        <Row items={[
          { label: "1 + Alt", value: result.ms1_alt15_pct },
          { label: "1 + Üst", value: result.ms1_ust15_pct },
          { label: "X + Alt", value: result.msx_alt15_pct },
          { label: "X + Üst", value: result.msx_ust15_pct },
          { label: "2 + Alt", value: result.ms2_alt15_pct },
          { label: "2 + Üst", value: result.ms2_ust15_pct },
        ]} />
      </Section>

      <Section title={lbl.comboKg}>
        <Row items={[
          { label: "1 + Var", value: result.ms1_kg_var_pct },
          { label: "1 + Yok", value: result.ms1_kg_yok_pct },
          { label: "X + Var", value: result.msx_kg_var_pct },
          { label: "X + Yok", value: result.msx_kg_yok_pct },
          { label: "2 + Var", value: result.ms2_kg_var_pct },
          { label: "2 + Yok", value: result.ms2_kg_yok_pct },
        ]} />
      </Section>

      {isFT && result.ht_kg_var_pct > 0 && (
        <Section title="Yarı KG Detayı">
          <SubLabel text="1. Yarı Karşılıklı Gol" />
          <Row items={[
            { label: "1Y KG Var", value: result.ht_kg_var_pct },
            { label: "1Y KG Yok", value: result.ht_kg_yok_pct },
          ]} />
          <SubLabel text="2. Yarı Karşılıklı Gol" />
          <Row items={[
            { label: "2Y KG Var", value: result.h2_kg_var_pct },
            { label: "2Y KG Yok", value: result.h2_kg_yok_pct },
          ]} />
          <SubLabel text="1. Yarı / 2. Yarı Karşılıklı Gol" />
          <Row items={[
            { label: "İY Var / 2Y Var", value: result.iy_h2_kg_vv_pct },
            { label: "İY Var / 2Y Yok", value: result.iy_h2_kg_vy_pct },
            { label: "İY Yok / 2Y Var", value: result.iy_h2_kg_yv_pct },
            { label: "İY Yok / 2Y Yok", value: result.iy_h2_kg_yy_pct },
          ]} />
          <SubLabel text="Her İki Yarıda da Gol" />
          <Row items={[
            { label: "Ev İki Yarıda", value: result.ev_iki_yari_gol_pct },
            { label: "Dep İki Yarıda", value: result.dep_iki_yari_gol_pct },
          ]} />
          <SubLabel text="Ev Sahibi Hangi Yarıda Daha Çok Gol Atar?" />
          <Row items={[
            { label: "1. Yarı", value: result.ev_encok_1y_pct },
            { label: "Eşit", value: result.ev_encok_esit_pct },
            { label: "2. Yarı", value: result.ev_encok_2y_pct },
          ]} />
          <SubLabel text="Deplasman Hangi Yarıda Daha Çok Gol Atar?" />
          <Row items={[
            { label: "1. Yarı", value: result.dep_encok_1y_pct },
            { label: "Eşit", value: result.dep_encok_esit_pct },
            { label: "2. Yarı", value: result.dep_encok_2y_pct },
          ]} />
        </Section>
      )}

      {isFT && (result.ht_result_1_pct > 0 || result.h2_result_1_pct > 0) && (
        <Section title="Yarı Sonuçları">
          {result.ht_result_1_pct > 0 && (
            <>
              <SubLabel text="1. Yarı Sonucu" />
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
              <SubLabel text="2. Yarı Sonucu" />
              <Row items={[
                { label: "2Y 1", value: result.h2_result_1_pct },
                { label: "2Y X", value: result.h2_result_x_pct },
                { label: "2Y 2", value: result.h2_result_2_pct },
              ]} />
            </>
          )}
        </Section>
      )}

      {result.score_freq && Object.keys(result.score_freq).length > 0 && (
        <Section title="Skor Sıklığı">
          <ScoreFreq freq={result.score_freq} />
        </Section>
      )}
    </div>
  );
}

export default function DetailedStats({ patternB, patternC, period }: Props) {
  const [open, setOpen] = useState(false);

  // localStorage'dan başlangıç state'ini hydration sonrası oku.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "1") setOpen(true);
    } catch {
      // erişim yoksa default kapalı
    }
  }, []);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {
      // ignore
    }
  };

  return (
    <div className="space-y-3">
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-colors"
        style={{
          backgroundColor: open ? "#0f1625" : "#0a0d14",
          borderColor: open ? "#1e293b" : "#1e293b",
          color: "#94a3b8",
        }}
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          <span className="text-base">🔬</span>
          <span className="text-sm font-semibold">Detaylı Analiz</span>
          <span className="text-[10px]" style={{ color: "#475569" }}>
            tüm pazarlar (~130 oran)
          </span>
        </span>
        <span className="text-xs font-mono" style={{ color: "#64748b" }}>
          {open ? "Gizle ▲" : "Göster ▼"}
        </span>
      </button>

      {open && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {patternB ? (
            <ArchiveDetailCard result={patternB} title="Arşiv 1 — Skor Seti" accentColor="#4ade80" period={period} />
          ) : (
            <div
              className="rounded-xl p-6 border flex items-center justify-center"
              style={{ backgroundColor: "#0a0d14", borderColor: "#1e293b" }}
            >
              <p className="text-sm" style={{ color: "#374151" }}>Arşiv 1: Yeterli veri yok</p>
            </div>
          )}
          {patternC ? (
            <ArchiveDetailCard result={patternC} title="Arşiv 2 — Oran Benzerliği" accentColor="#c084fc" period={period} />
          ) : (
            <div
              className="rounded-xl p-6 border flex items-center justify-center"
              style={{ backgroundColor: "#0a0d14", borderColor: "#1e293b" }}
            >
              <p className="text-sm" style={{ color: "#374151" }}>Arşiv 2: Yeterli veri yok</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
