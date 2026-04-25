"use client";

import { useEffect } from "react";

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: Props) {
  useEffect(() => {
    // Loglamak istersen Sentry/Logtail vs buraya
    console.error("[GlobalError]", error);
  }, [error]);

  return (
    <div className="flex items-center justify-center min-h-[60vh] p-6">
      <div
        className="max-w-md w-full rounded-xl p-6 border text-center space-y-4"
        style={{ backgroundColor: "#1c0816", borderColor: "#7f1d1d" }}
      >
        <div className="text-4xl">💥</div>
        <h2 className="text-base font-bold" style={{ color: "#f87171" }}>
          Bir şeyler ters gitti
        </h2>
        <p className="text-xs" style={{ color: "#94a3b8" }}>
          {error.message || "Beklenmeyen bir hata oluştu."}
        </p>
        {error.digest && (
          <p className="text-[10px] font-mono" style={{ color: "#475569" }}>
            ID: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          className="text-xs px-4 py-2 rounded font-semibold transition-colors bg-red-900 hover:bg-red-800 text-red-100"
        >
          Tekrar dene
        </button>
      </div>
    </div>
  );
}
