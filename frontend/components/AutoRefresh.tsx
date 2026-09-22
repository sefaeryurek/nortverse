"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function AutoRefresh({ intervalMs = 45_000 }: { intervalMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    let lastRefreshAt = 0;
    const refreshVisible = () => {
      if (document.visibilityState !== "visible" || Date.now() - lastRefreshAt < 5_000) return;
      lastRefreshAt = Date.now();
      router.refresh();
    };
    const timer = window.setInterval(refreshVisible, intervalMs);
    document.addEventListener("visibilitychange", refreshVisible);
    window.addEventListener("focus", refreshVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refreshVisible);
      window.removeEventListener("focus", refreshVisible);
    };
  }, [intervalMs, router]);
  return null;
}
