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
    barColor: "var(--nv-accent-green)",
  },
  x: {
    labelColor: "var(--nv-accent-amber)",
    badgeBg: "var(--nv-accent-amber-dim)",
    badgeColor: "var(--nv-accent-amber)",
    badgeBorder: "var(--nv-accent-amber)",
    barColor: "var(--nv-accent-amber)",
  },
  "2": {
    labelColor: "var(--nv-accent-red)",
    badgeBg: "var(--nv-accent-red-dim)",
    badgeColor: "var(--nv-accent-red)",
    badgeBorder: "var(--nv-accent-red)",
    barColor: "var(--nv-accent-red)",
  },
};

/** Compute opacity for a score based on its position (first = 1.0, last = 0.6). */
function getOpacity(index: number, total: number): number {
  if (total <= 1) return 1.0;
  return 1.0 - (index / (total - 1)) * 0.4;
}

/** Compute the width percentage for the frequency bar under each badge. */
function getBarWidth(index: number): string {
  if (index === 0) return "100%";
  if (index === 1) return "85%";
  if (index === 2) return "70%";
  return "50%";
}

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
          {scores.map((score, index) => (
            <div
              key={score}
              style={{
                position: "relative",
                display: "inline-flex",
                flexDirection: "column",
                alignItems: "center",
                opacity: getOpacity(index, scores.length),
              }}
            >
              {/* Score badge */}
              <span
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

              {/* Top score accent dot */}
              {index === 0 && (
                  <span
                    aria-hidden="true"
                    style={{
                      position: "absolute",
                      top: -3,
                      right: -3,
                      width: 8,
                      height: 8,
                      borderRadius: "var(--nv-radius-full)",
                      backgroundColor: s.barColor,
                      border: "2px solid var(--nv-bg-card)",
                    }}
                  />
              )}

              {/* Frequency bar */}
              <div
                style={{
                  width: "100%",
                  display: "flex",
                  justifyContent: "center",
                  marginTop: 2,
                }}
              >
                <div
                  style={{
                    width: getBarWidth(index),
                    height: 3,
                    borderRadius: "var(--nv-radius-full)",
                    backgroundColor: s.barColor,
                    opacity: 0.6,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
