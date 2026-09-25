export default function SonuclarLoading() {
  return (
    <div
      className="grid gap-3 px-[var(--nv-page-gutter)] py-4"
      style={{ maxWidth: "var(--nv-max-content)" }}
    >
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="nv-card p-4">
          <div className="flex items-center gap-3">
            <div className="nv-skeleton" style={{ width: 60, height: 14 }} />
            <div className="nv-skeleton" style={{ width: 40, height: 14 }} />
            <div className="flex-1" />
            <div className="nv-skeleton" style={{ width: 56, height: 28 }} />
          </div>
          <div className="flex items-center gap-3 mt-3">
            <div className="nv-skeleton flex-1" style={{ height: 14 }} />
            <div className="nv-skeleton" style={{ width: 16, height: 10 }} />
            <div className="nv-skeleton flex-1" style={{ height: 14 }} />
          </div>
          <div className="flex justify-end mt-3">
            <div className="nv-skeleton" style={{ width: 64, height: 28 }} />
          </div>
        </div>
      ))}
    </div>
  );
}
