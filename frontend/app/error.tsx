"use client";

import { useEffect } from "react";

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: Props) {
  useEffect(() => {
    console.error("[GlobalError]", error);
  }, [error]);

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
          borderColor: "var(--nv-accent-red)",
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            margin: "0 auto var(--nv-space-lg)",
            borderRadius: "var(--nv-radius-full)",
            backgroundColor: "var(--nv-accent-red-dim)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "24px",
          }}
        >
          !
        </div>

        <h2
          style={{
            fontSize: "var(--nv-text-lg)",
            fontWeight: 700,
            color: "var(--nv-accent-red)",
            marginBottom: "var(--nv-space-sm)",
          }}
        >
          Bir şeyler ters gitti
        </h2>

        <p
          style={{
            fontSize: "var(--nv-text-xs)",
            color: "var(--nv-text-secondary)",
            marginBottom: "var(--nv-space-sm)",
          }}
        >
          {error.message || "Beklenmeyen bir hata oluştu."}
        </p>

        {error.digest && (
          <p
            style={{
              fontSize: "10px",
              fontFamily: "var(--nv-font-mono)",
              color: "var(--nv-text-tertiary)",
              marginBottom: "var(--nv-space-lg)",
            }}
          >
            ID: {error.digest}
          </p>
        )}

        <button
          onClick={reset}
          style={{
            fontSize: "var(--nv-text-xs)",
            fontWeight: 600,
            padding: "8px 20px",
            borderRadius: "var(--nv-radius-lg)",
            border: "none",
            cursor: "pointer",
            backgroundColor: "var(--nv-accent-red)",
            color: "var(--nv-text-on-accent)",
            transition: `opacity var(--nv-duration-normal) var(--nv-ease)`,
          }}
        >
          Tekrar dene
        </button>
      </div>
    </div>
  );
}
