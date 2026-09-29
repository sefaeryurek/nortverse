export default function Loading() {
  return (
    <div
      className="grid gap-3 px-[var(--nv-page-gutter)] py-4"
      style={{ maxWidth: "var(--nv-max-content)" }}
    >
      {/* Özet kartları skeleton */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="nv-card p-4">
            <div className="nv-skeleton mb-2" style={{ width: 80, height: 12 }} />
            <div className="nv-skeleton" style={{ width: 48, height: 24 }} />
          </div>
        ))}
      </div>
      {/* Maç satırları skeleton */}
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="nv-card p-4">
          <div className="flex items-center gap-3">
            <div className="nv-skeleton" style={{ width: 60, height: 14 }} />
            <div className="nv-skeleton flex-1" style={{ height: 14 }} />
            <div className="nv-skeleton" style={{ width: 56, height: 28 }} />
          </div>
          <div className="flex items-center gap-2 mt-3">
            <div className="nv-skeleton" style={{ width: 60, height: 20 }} />
            <div className="nv-skeleton" style={{ width: 60, height: 20 }} />
            <div className="nv-skeleton" style={{ width: 60, height: 20 }} />
          </div>
        </div>
      ))}
    </div>
  );
}
