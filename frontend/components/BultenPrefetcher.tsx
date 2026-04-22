"use client";

import { useEffect } from "react";
import { prefetchAnalyze } from "@/lib/api";

interface Props {
  matchIds: string[];
}

export default function BultenPrefetcher({ matchIds }: Props) {
  useEffect(() => {
    // Sadece ilk 3 maçı prefetch et — daha fazlası eşzamanlı Playwright yükü oluşturur
    matchIds.slice(0, 3).forEach((id) => prefetchAnalyze(id));
  }, [matchIds]);

  return null;
}
