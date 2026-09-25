export default function BultenLoading() {
  return (
    <div style={{ padding: "var(--nv-space-sm) var(--nv-page-gutter)" }}>
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="nv-card"
          style={{
            marginBottom: "var(--nv-space-sm)",
            padding: "var(--nv-space-md) var(--nv-space-lg)",
            display: "flex",
            alignItems: "center",
            gap: "var(--nv-space-md)",
          }}
        >
          <div
            className="nv-skeleton"
            style={{
              width: 52,
              height: 36,
              flexShrink: 0,
              borderRadius: "var(--nv-radius-sm)",
            }}
          />
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
            <div
              className="nv-skeleton"
              style={{ width: 20, height: 20, borderRadius: "var(--nv-radius-full)" }}
            />
            <div
              className="nv-skeleton"
              style={{ width: 72, height: 12, borderRadius: "var(--nv-radius-sm)" }}
            />
          </div>
          <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8 }}>
            <div
              className="nv-skeleton"
              style={{ height: 14, flex: 1, borderRadius: "var(--nv-radius-sm)" }}
            />
            <div
              className="nv-skeleton"
              style={{ width: 24, height: 12, borderRadius: "var(--nv-radius-sm)" }}
            />
            <div
              className="nv-skeleton"
              style={{ height: 14, flex: 1, borderRadius: "var(--nv-radius-sm)" }}
            />
          </div>
          <div
            className="nv-skeleton"
            style={{ width: 28, height: 28, borderRadius: "var(--nv-radius-full)", flexShrink: 0 }}
          />
        </div>
      ))}
    </div>
  );
}
