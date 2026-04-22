"use client";

import { useEffect } from "react";
import { prefetchAnalyze } from "@/lib/api";

interface Props {
  matchIds: string[];
}

export default function BultenPrefetcher({ matchIds }: Props) {
  useEffect(() => {
    // Tüm maçların analizini arka planda başlat
    // Kullanıcı bir maça tıkladığında cache'ten anında gelir
    for (const id of matchIds) {
      prefetchAnalyze(id);
    }
  }, [matchIds]);

  return null;
}
