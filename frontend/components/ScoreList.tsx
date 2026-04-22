interface Props {
  scores: string[];
  type: "1" | "x" | "2";
  label: string;
}

const COLORS = {
  "1": { bg: "#052e16", border: "#166534", text: "#86efac", dot: "#4ade80" },
  x: { bg: "#1c1917", border: "#44403c", text: "#d6d3d1", dot: "#a8a29e" },
  "2": { bg: "#1c0816", border: "#86198f", text: "#f0abfc", dot: "#d946ef" },
};

export default function ScoreList({ scores, type, label }: Props) {
  const c = COLORS[type];

  return (
    <div className="flex-1 min-w-0">
      <div
        className="text-xs font-semibold uppercase tracking-wider mb-2 px-1"
        style={{ color: c.dot }}
      >
        {label}
        <span
          className="ml-2 text-[10px] font-bold px-1.5 py-0.5 rounded"
          style={{ backgroundColor: c.bg, color: c.text }}
        >
          {scores.length}
        </span>
      </div>
      {scores.length === 0 ? (
        <p className="text-xs px-1" style={{ color: "#475569" }}>
          —
        </p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {scores.map((s) => (
            <span
              key={s}
              className="text-xs px-2 py-1 rounded border font-mono font-semibold"
              style={{ backgroundColor: c.bg, color: c.text, borderColor: c.border }}
            >
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
