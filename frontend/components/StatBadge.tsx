interface Props {
  value: number;
  label?: string;
  size?: "sm" | "md";
}

export default function StatBadge({ value, label, size = "md" }: Props) {
  const pct = Math.round(value);

  // Color tiers using --nv- tokens
  const tier =
    pct >= 75
      ? { bg: "var(--nv-accent-green-dim)", color: "var(--nv-accent-green)", border: "var(--nv-accent-green)" }
      : pct >= 60
        ? { bg: "var(--nv-accent-blue-dim)", color: "var(--nv-accent-blue)", border: "var(--nv-accent-blue)" }
        : pct >= 40
          ? { bg: "var(--nv-accent-amber-dim)", color: "var(--nv-accent-amber)", border: "var(--nv-accent-amber)" }
          : { bg: "var(--nv-accent-red-dim)", color: "var(--nv-accent-red)", border: "var(--nv-accent-red)" };

  const padding = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1.5 text-sm";

  return (
    <div
      className={`${padding} rounded font-bold text-center`}
      style={{
        backgroundColor: tier.bg,
        color: tier.color,
        border: `1px solid ${tier.border}`,
        borderRadius: "var(--nv-radius-sm)",
        fontFamily: "var(--nv-font-mono)",
        minWidth: size === "sm" ? 44 : 56,
        opacity: pct < 40 ? 0.7 : 1,
      }}
    >
      {pct}%
      {label && (
        <div
          className="text-[10px] font-normal mt-0.5"
          style={{ color: tier.color, opacity: 0.8 }}
        >
          {label}
        </div>
      )}
    </div>
  );
}
