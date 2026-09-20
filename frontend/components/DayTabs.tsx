import Link from "next/link";

const DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

export function getRollingDates(now = new Date(), todayIso = now.toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" }), range: "upcoming" | "past" = "upcoming"): { label: string; date: string; today: boolean }[] {
  return Array.from({ length: 8 }, (_, i) => {
    const d = new Date(`${todayIso}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + (range === "past" ? -i : i - 1));
    const iso = d.toISOString().slice(0, 10);
    const dayIdx = (d.getUTCDay() + 6) % 7; // 0=Pzt
    return { label: DAYS[dayIdx], date: iso, today: iso === todayIso };
  });
}

interface Props {
  activeDate: string;
  basePath?: string;
  referenceDate?: string;
  range?: "upcoming" | "past";
}

export default function DayTabs({ activeDate, basePath = "/bulten", referenceDate, range = "upcoming" }: Props) {
  const days = getRollingDates(undefined, referenceDate, range);

  return (
    <div
      className="flex gap-1 p-3 border-b overflow-x-auto"
      style={{ borderColor: "#2d3748" }}
    >
      {days.map(({ label, date, today }) => {
        const active = date === activeDate;
        const className = "flex-shrink-0 flex flex-col items-center px-4 py-2 rounded-lg text-xs font-semibold transition-colors";
        const style = {
          backgroundColor: active ? "#1d4ed8" : today ? "#1e3a5f" : "#1c2333",
          color: active ? "#fff" : today ? "#93c5fd" : "#94a3b8",
          border: `1px solid ${active ? "#2563eb" : "#2d3748"}`,
        };
        const content = <><span>{label}</span><span className="text-[10px] font-normal mt-0.5 opacity-70">
          {date.slice(5).replace("-", "/")}
        </span></>;
        return active ? (
          <span key={date} aria-current="date" className={className} style={style}>{content}</span>
        ) : (
          <Link key={date} href={`${basePath}?date=${date}`} prefetch={false}
            aria-label={`${date} tarihindeki maçlar`} className={className} style={style}>
            {content}
          </Link>
        );
      })}
    </div>
  );
}
