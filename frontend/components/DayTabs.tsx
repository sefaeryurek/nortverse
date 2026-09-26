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
  const effectiveRange = basePath === "/sonuclar" ? "past" : range;
  const days = getRollingDates(undefined, referenceDate, effectiveRange);

  return (
    <nav aria-label={effectiveRange === "past" ? "Sonuç tarihleri: bugün ve önceki 7 gün" : "Bülten tarihleri"}>
      {effectiveRange === "past" && (
        <p
          className="px-4 pt-3 pb-1"
          style={{
            fontSize: "var(--nv-text-xs)",
            color: "var(--nv-text-tertiary)",
          }}
        >
          Bugün ve önceki 7 gün
        </p>
      )}
      <div
        className="flex gap-2 px-4 py-3 overflow-x-auto nv-hide-scrollbar"
        style={{
          borderBottom: "1px solid var(--nv-border)",
          scrollbarWidth: "none",
          /* Hide scrollbar for WebKit */
          WebkitOverflowScrolling: "touch",
        } as React.CSSProperties}
      >
        {days.map(({ label, date, today }) => {
          const active = date === activeDate;
          const baseStyle: React.CSSProperties = {
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "2px",
            padding: "6px 16px",
            borderRadius: "var(--nv-radius-full)",
            fontFamily: "var(--nv-font-mono)",
            fontSize: "var(--nv-text-xs)",
            fontWeight: 600,
            letterSpacing: "var(--nv-tracking-wide)",
            textDecoration: "none",
            transition: `background-color var(--nv-duration-normal) var(--nv-ease), color var(--nv-duration-normal) var(--nv-ease), box-shadow var(--nv-duration-normal) var(--nv-ease)`,
            backgroundColor: active
              ? "var(--nv-accent-blue)"
              : "var(--nv-bg-card)",
            color: active
              ? "var(--nv-text-on-accent)"
              : "var(--nv-text-secondary)",
            boxShadow: active
              ? "var(--nv-shadow-glow-blue)"
              : "none",
            border: `1px solid ${active ? "var(--nv-accent-blue)" : "var(--nv-border)"}`,
          };

          const content = (
            <>
              <span>{label}</span>
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: 400,
                  opacity: active ? 0.85 : 0.6,
                }}
              >
                {date.slice(5).replace("-", "/")}
              </span>
              {/* Bugun isaretcisi - kucuk nokta */}
              {today && (
                <span
                  style={{
                    width: 4,
                    height: 4,
                    borderRadius: "var(--nv-radius-full)",
                    backgroundColor: active
                      ? "var(--nv-text-on-accent)"
                      : "var(--nv-accent-blue)",
                    marginTop: 1,
                  }}
                />
              )}
            </>
          );

          return active ? (
            <span
              key={date}
              aria-current="date"
              style={baseStyle}
            >
              {content}
            </span>
          ) : (
            <Link
              key={date}
              href={`${basePath}?date=${date}`}
              prefetch={false}
              aria-label={`${date} tarihindeki maçlar`}
              className="nv-daytab-inactive"
              style={baseStyle}
            >
              {content}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
