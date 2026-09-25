interface Props {
  scores: string[];
  type: "1" | "x" | "2";
  label: string;
}

const TYPE_STYLES = {
  "1": {
    labelColor: "var(--nv-accent-green)",
    badgeBg: "var(--nv-accent-green-dim)",
    badgeColor: "var(--nv-accent-green)",
    badgeBorder: "var(--nv-accent-green)",
  },
  x: {
    labelColor: "var(--nv-accent-amber)",
    badgeBg: "var(--nv-accent-amber-dim)",
    badgeColor: "var(--nv-accent-amber)",
    badgeBorder: "var(--nv-accent-amber)",
  },
  "2": {
    labelColor: "var(--nv-accent-red)",
    badgeBg: "var(--nv-accent-red-dim)",
    badgeColor: "var(--nv-accent-red)",
    badgeBorder: "var(--nv-accent-red)",
  },
};

export default function ScoreList({ scores, type, label }: Props) {
  const s = TYPE_STYLES[type];

  return (
    <div className="flex-1 min-w-0">
      <div
        className="text-xs font-semibold uppercase mb-2 px-1 flex items-center gap-2"
        style={{
          color: s.labelColor,
          letterSpacing: "var(--nv-tracking-wide)",
          fontSize: "var(--nv-text-xs)",
        }}
      >
        {label}
        <span
          className="nv-badge"
          style={{
            backgroundColor: s.badgeBg,
            color: s.badgeColor,
          }}
        >
          {scores.length}
        </span>
      </div>
      {scores.length === 0 ? (
        <p
          className="text-xs px-1"
          style={{ color: "var(--nv-text-tertiary)" }}
        >
          —
        </p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {scores.map((score) => (
            <span
              key={score}
              className="text-xs px-2.5 py-1 font-semibold"
              style={{
                backgroundColor: s.badgeBg,
                color: s.badgeColor,
                border: `1px solid ${s.badgeBorder}`,
                borderRadius: "var(--nv-radius-full)",
                fontFamily: "var(--nv-font-mono)",
                fontSize: "var(--nv-text-xs)",
              }}
            >
              {score}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
