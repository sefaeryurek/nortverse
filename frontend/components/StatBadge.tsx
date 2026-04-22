interface Props {
  value: number;
  label?: string;
  size?: "sm" | "md";
}

export default function StatBadge({ value, label, size = "md" }: Props) {
  const pct = Math.round(value);

  const bg =
    pct >= 60 ? "#064e3b" : pct >= 40 ? "#451a03" : "#1f1720";
  const text =
    pct >= 60 ? "#6ee7b7" : pct >= 40 ? "#fcd34d" : "#f87171";
  const border =
    pct >= 60 ? "#065f46" : pct >= 40 ? "#92400e" : "#7f1d1d";

  const padding = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1.5 text-sm";

  return (
    <div
      className={`${padding} rounded font-bold text-center border`}
      style={{ backgroundColor: bg, color: text, borderColor: border, minWidth: size === "sm" ? 44 : 56 }}
    >
      {pct}%
      {label && (
        <div className="text-[10px] font-normal mt-0.5" style={{ color: text, opacity: 0.8 }}>
          {label}
        </div>
      )}
    </div>
  );
}
