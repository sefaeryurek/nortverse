export default function AnalyzeLoading() {
  return (
    <div className="flex h-full flex-col pb-[60px] md:pb-0">
      {/* Header skeleton */}
      <div
        className="px-5 py-4 flex items-center gap-3 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--nv-border)" }}
      >
        <div className="nv-skeleton w-8 h-8 rounded-full flex-shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="nv-skeleton h-5 w-64 max-w-full" style={{ borderRadius: "var(--nv-radius-sm)" }} />
          <div className="nv-skeleton h-3 w-40 max-w-full" style={{ borderRadius: "var(--nv-radius-sm)" }} />
        </div>
      </div>

      {/* Content skeleton */}
      <div className="flex-1 p-4 space-y-4">
        {/* Period tabs skeleton */}
        <div className="flex gap-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="nv-skeleton h-9 w-24"
              style={{ borderRadius: "var(--nv-radius-full)" }}
            />
          ))}
        </div>

        {/* Trends skeleton */}
        <div className="nv-card p-4 space-y-3" style={{ borderRadius: "var(--nv-radius-lg)" }}>
          <div className="nv-skeleton h-4 w-48" style={{ borderRadius: "var(--nv-radius-sm)" }} />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="nv-skeleton h-36"
                style={{ borderRadius: "var(--nv-radius-md)" }}
              />
            ))}
          </div>
        </div>

        {/* Score list skeleton */}
        <div className="nv-card p-4 space-y-3" style={{ borderRadius: "var(--nv-radius-lg)" }}>
          <div className="nv-skeleton h-4 w-56" style={{ borderRadius: "var(--nv-radius-sm)" }} />
          <div className="flex gap-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex-1 space-y-2">
                <div className="nv-skeleton h-3 w-20" style={{ borderRadius: "var(--nv-radius-sm)" }} />
                <div className="flex flex-wrap gap-1.5">
                  {[1, 2, 3].map((j) => (
                    <div
                      key={j}
                      className="nv-skeleton h-7 w-12"
                      style={{ borderRadius: "var(--nv-radius-full)" }}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Picks skeleton */}
        <div className="nv-card p-4 space-y-3" style={{ borderRadius: "var(--nv-radius-lg)" }}>
          <div className="nv-skeleton h-4 w-44" style={{ borderRadius: "var(--nv-radius-sm)" }} />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="nv-skeleton h-16"
                style={{ borderRadius: "var(--nv-radius-md)" }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
