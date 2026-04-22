"use client";

import { useRouter, useSearchParams } from "next/navigation";

const DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

function getWeekDates(): { label: string; date: string; today: boolean }[] {
  const now = new Date();
  const dayOfWeek = now.getDay(); // 0=Sun, 1=Mon...
  const monday = new Date(now);
  monday.setDate(now.getDate() - ((dayOfWeek + 6) % 7));

  return DAYS.map((label, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    const iso = d.toISOString().split("T")[0];
    const todayIso = now.toISOString().split("T")[0];
    return { label, date: iso, today: iso === todayIso };
  });
}

interface Props {
  activeDate: string;
}

export default function DayTabs({ activeDate }: Props) {
  const router = useRouter();
  const days = getWeekDates();

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
            onClick={() => router.push(`/bulten?date=${date}`)}
            className="flex-shrink-0 flex flex-col items-center px-4 py-2 rounded-lg text-xs font-semibold transition-colors"
            style={{
              backgroundColor: active ? "#1d4ed8" : today ? "#1e3a5f" : "#1c2333",
              color: active ? "#fff" : today ? "#93c5fd" : "#94a3b8",
              border: `1px solid ${active ? "#2563eb" : "#2d3748"}`,
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
