"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";

export default function RetryButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return (
    <button
      disabled={pending}
      onClick={() => startTransition(() => router.refresh())}
      style={{
        backgroundColor: "var(--nv-accent-blue)",
        color: "#ffffff",
        fontFamily: "var(--nv-font-sans)",
        fontSize: "var(--nv-text-sm)",
        fontWeight: 600,
        padding: "8px 20px",
        borderRadius: "var(--nv-radius-lg)",
        border: "none",
        cursor: pending ? "not-allowed" : "pointer",
        opacity: pending ? 0.5 : 1,
        transition: `opacity var(--nv-duration-normal) var(--nv-ease), box-shadow var(--nv-duration-normal) var(--nv-ease)`,
        boxShadow: "var(--nv-shadow-glow-blue)",
      }}
    >
      {pending ? "Yeniden yükleniyor…" : "Tekrar dene"}
    </button>
  );
}
