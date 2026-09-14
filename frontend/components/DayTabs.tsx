"use client";

import { useRouter } from "next/navigation";

const DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

export function getRollingDates(now = new Date(), todayIso = now.toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" })): { label: string; date: string; today: boolean }[] {
  // Dün + bugün + 6 gün = 8 günlük pencere
  return Array.from({ length: 8 }, (_, i) => {
    const d = new Date(`${todayIso}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() - 1 + i);
    const iso = d.toISOString().slice(0, 10);
    const dayIdx = (d.getUTCDay() + 6) % 7; // 0=Pzt
    return { label: DAYS[dayIdx], date: iso, today: iso === todayIso };
  });
}

interface Props {
  activeDate: string;
  basePath?: string;
  referenceDate?: string;
}

export default function DayTabs({ activeDate, basePath = "/bulten", referenceDate }: Props) {
  const router = useRouter();
  const days = getRollingDates(undefined, referenceDate);

  return (
    <div
      className="flex gap-1 p-3 border-b overflow-x-auto"
      style={{ borderColor: "#2d3748" }}
    >
      {days.map(({ label, date, today }) => {
        const active = date === activeDate;
        return (
          <button
            key={date}
            onClick={() => {
              if (active) return; // aynı tarihe tıklamak gereksiz reload üretmesin
              router.push(`${basePath}?date=${date}`);
            }}
            disabled={active}
            className="flex-shrink-0 flex flex-col items-center px-4 py-2 rounded-lg text-xs font-semibold transition-colors"
            style={{
              backgroundColor: active ? "#1d4ed8" : today ? "#1e3a5f" : "#1c2333",
              color: active ? "#fff" : today ? "#93c5fd" : "#94a3b8",
              border: `1px solid ${active ? "#2563eb" : "#2d3748"}`,
              cursor: active ? "default" : "pointer",
            }}
          >
            <span>{label}</span>
            <span className="text-[10px] font-normal mt-0.5 opacity-70">
              {date.slice(5).replace("-", "/")}
            </span>
          </button>
        );
      })}
    </div>
  );
}
