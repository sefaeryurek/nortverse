import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import BultenRow from "@/components/BultenRow";
import { getFixture } from "@/lib/api";

interface Props {
  searchParams: Promise<{ date?: string }>;
}

async function MatchList({ date }: { date: string }) {
  let matches = [];
  let error = "";
  try {
    matches = await getFixture(date);
  } catch (e) {
    error = e instanceof Error ? e.message : "Bağlantı hatası";
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="text-4xl mb-3">⚠️</div>
          <p className="text-sm" style={{ color: "#ef4444" }}>
            {error}
          </p>
          <p className="text-xs mt-1" style={{ color: "#475569" }}>
            Backend sunucusunun çalıştığından emin olun
          </p>
        </div>
      </div>
    );
  }

  if (matches.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="text-4xl mb-3">📭</div>
          <p className="text-sm" style={{ color: "#64748b" }}>
            Bu tarihte Hot maç bulunamadı.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        className="px-4 py-2 text-xs font-medium border-b"
        style={{ color: "#64748b", borderColor: "#2d3748" }}
      >
        {matches.length} maç bulundu
      </div>
      {matches.map((m) => (
        <BultenRow key={m.match_id} match={m} />
      ))}
    </div>
  );
}

export default async function BultenPage({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toISOString().split("T")[0];
  const date = params.date ?? today;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="px-6 py-4 border-b flex items-center justify-between"
        style={{ borderColor: "#2d3748" }}
      >
        <div>
          <h1 className="text-lg font-bold" style={{ color: "#e2e8f0" }}>
            Günlük Bülten
          </h1>
          <p className="text-xs mt-0.5" style={{ color: "#64748b" }}>
            Hot maçlar — Nowgoal verisi
          </p>
        </div>
        <span
          className="text-xs px-2.5 py-1 rounded-full"
          style={{ backgroundColor: "#1e3a5f", color: "#93c5fd" }}
        >
          {date}
        </span>
      </div>

      {/* Gün sekmeleri */}
      <DayTabs activeDate={date} />

      {/* Maç listesi */}
      <div className="flex-1 overflow-y-auto">
        <Suspense
          fallback={
            <div className="flex items-center justify-center py-20">
              <p className="text-sm animate-pulse" style={{ color: "#64748b" }}>
                Yükleniyor...
              </p>
            </div>
          }
        >
          <MatchList date={date} />
        </Suspense>
      </div>
    </div>
  );
}
