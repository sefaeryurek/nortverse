import Link from "next/link";

export default function NotFound() {
  return (
    <div
      className="flex items-center justify-center p-6"
      style={{ minHeight: "60vh" }}
    >
      <div
        className="nv-card nv-fade-in"
        style={{
          maxWidth: 420,
          width: "100%",
          padding: "var(--nv-space-2xl)",
          textAlign: "center",
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            margin: "0 auto var(--nv-space-lg)",
            borderRadius: "var(--nv-radius-full)",
            backgroundColor: "var(--nv-accent-amber-dim)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "24px",
            fontFamily: "var(--nv-font-mono)",
            fontWeight: 700,
            color: "var(--nv-accent-amber)",
          }}
        >
          404
        </div>

        <h2
          style={{
            fontSize: "var(--nv-text-lg)",
            fontWeight: 700,
            color: "var(--nv-text-primary)",
            marginBottom: "var(--nv-space-sm)",
          }}
        >
          Sayfa bulunamadı
        </h2>

        <p
          style={{
            fontSize: "var(--nv-text-xs)",
            color: "var(--nv-text-secondary)",
            marginBottom: "var(--nv-space-lg)",
          }}
        >
          Aradığınız sayfa mevcut değil veya taşınmış olabilir.
        </p>

        <Link
          href="/bulten"
          style={{
            display: "inline-block",
            fontSize: "var(--nv-text-xs)",
            fontWeight: 600,
            padding: "8px 20px",
            borderRadius: "var(--nv-radius-lg)",
            backgroundColor: "var(--nv-accent-blue)",
            color: "var(--nv-text-on-accent)",
            textDecoration: "none",
            transition: `opacity var(--nv-duration-normal) var(--nv-ease)`,
          }}
        >
          Bültene dön
        </Link>
      </div>
    </div>
  );
}
