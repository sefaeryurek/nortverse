export default function CanliLoading() {
  return (
    <div
      className="grid gap-3 px-[var(--nv-page-gutter)] py-4"
      style={{ maxWidth: "var(--nv-max-content)" }}
    >
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="nv-card p-4">
          <div className="flex items-center gap-3">
            <div className="nv-skeleton" style={{ width: 60, height: 14 }} />
            <div className="flex-1" />
            <div className="nv-skeleton" style={{ width: 64, height: 36 }} />
          </div>
          <div className="flex items-center gap-3 mt-3">
            <div className="nv-skeleton flex-1" style={{ height: 14 }} />
            <div className="nv-skeleton" style={{ width: 16, height: 10 }} />
            <div className="nv-skeleton flex-1" style={{ height: 14 }} />
          </div>
          <div className="mt-3">
            <div className="nv-skeleton" style={{ width: "100%", height: 6 }} />
          </div>
        </div>
      ))}
    </div>
  );
}
