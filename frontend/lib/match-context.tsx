"use client";

import { createContext, useContext, type ReactNode } from "react";

export interface MatchInfo {
  matchId: string;
  homeTeam: string;
  awayTeam: string;
}

const MatchContext = createContext<MatchInfo | null>(null);

export function MatchProvider({ value, children }: { value: MatchInfo; children: ReactNode }) {
  return <MatchContext.Provider value={value}>{children}</MatchContext.Provider>;
}

/**
 * Analyze sayfasında match metadata'sını paylaşır.
 * Sayfa context dışındaysa null döner — bu durumda "+" butonu görünmez.
 */
export function useMatchInfo(): MatchInfo | null {
  return useContext(MatchContext);
}
