"use client";

import { useEffect } from "react";
import { prefetchAnalyze } from "@/lib/api";

interface Props {
  matchIds: string[];
}

export default function BultenPrefetcher({ matchIds }: Props) {
  useEffect(() => {
    // İlk 5 maçı prefetch et — Supabase pool_size=2 limiti için dengeli sayı
    matchIds.slice(0, 5).forEach((id) => prefetchAnalyze(id));
  }, [matchIds]);

  return null;
}
