"use client";

import { useState, type FormEvent } from "react";
import { useLocale } from "@/lib/locale-context";
import { DEFAULT_NEXT, safeNext } from "@/lib/safe-next";

/** Güvenli dönüş adresi: sadece aynı sitenin yolu (Sprint 94 E4 — kodlanmış ters bölü / sekme hileleri dahil). */
function nextTarget(): string {
  if (typeof window === "undefined") return DEFAULT_NEXT;
  return safeNext(new URLSearchParams(window.location.search).get("next"), window.location.origin);
}

export default function LoginPage() {
  const { t } = useLocale();
  const a = t.auth;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (res.ok) {
        // Tam sayfa geçişi: proxy ve sunucu tarafı veriler yeni çerezle yeniden çalışsın
        window.location.assign(nextTarget());
        return;
      }
      setError(res.status === 429 ? a.locked : res.status === 401 ? a.wrong : a.failed);
    } catch {
      setError(a.failed);
    }
    setBusy(false);
  }

  const inputStyle = {
    fontSize: "var(--nv-text-base)",
    color: "var(--nv-text-primary)",
    backgroundColor: "var(--nv-bg-elevated)",
    border: "1px solid var(--nv-border)",
    borderRadius: "var(--nv-radius-md)",
  } as const;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center px-4" style={{ backgroundColor: "var(--nv-bg-base)" }}>
      <form onSubmit={onSubmit} className="nv-card w-full max-w-sm p-6 space-y-4" aria-labelledby="login-title">
        <div>
          <h1 id="login-title" className="font-bold" style={{ fontSize: "var(--nv-text-xl)", color: "var(--nv-text-primary)" }}>
            Nortverse · {a.title}
          </h1>
          <p className="mt-1" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-tertiary)" }}>{a.subtitle}</p>
        </div>
        <label className="block space-y-1">
          <span style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>{a.username}</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            required
            className="w-full px-3 py-2"
            style={inputStyle}
          />
        </label>
        <label className="block space-y-1">
          <span style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>{a.password}</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
            className="w-full px-3 py-2"
            style={inputStyle}
          />
        </label>
        {error && (
          <p role="alert" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}>{error}</p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="w-full py-2.5 font-semibold transition-opacity disabled:opacity-60"
          style={{ fontSize: "var(--nv-text-sm)", backgroundColor: "var(--nv-accent-blue)", color: "var(--nv-text-on-accent)", borderRadius: "var(--nv-radius-md)" }}
        >
          {busy ? a.submitting : a.submit}
        </button>
        <p style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{a.noAccount}</p>
      </form>
    </div>
  );
}
