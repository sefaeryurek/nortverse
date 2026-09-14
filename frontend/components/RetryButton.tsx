"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";

export default function RetryButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return <button disabled={pending} onClick={() => startTransition(() => router.refresh())}
    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50">
    {pending ? "Yeniden yükleniyor…" : "Tekrar dene"}
  </button>;
}
