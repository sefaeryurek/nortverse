export interface FixtureMatch {
  match_id: string;
  home_team: string;
  away_team: string;
  league_code: string;
  league_name: string | null;
  kickoff_time: string | null;
}

export interface PeriodOut {
  scores_1: string[];
  scores_x: string[];
  scores_2: string[];
}

export interface PatternResult {
  match_count: number;
  // Maç Sonucu
  result_1_pct: number;
  result_x_pct: number;
  result_2_pct: number;
  // Çifte Şans
  dc_1x_pct: number;
  dc_x2_pct: number;
  dc_12_pct: number;
  // Alt / Üst
  alt_15_pct: number;
  ust_15_pct: number;
  alt_25_pct: number;
  ust_25_pct: number;
  alt_35_pct: number;
  ust_35_pct: number;
  // KG
  kg_var_pct: number;
  kg_yok_pct: number;
  // Handikap
  hnd_h20_1_pct: number;
  hnd_h20_x_pct: number;
  hnd_h20_2_pct: number;
  hnd_h10_1_pct: number;
  hnd_h10_x_pct: number;
  hnd_h10_2_pct: number;
  hnd_a10_1_pct: number;
  hnd_a10_x_pct: number;
  hnd_a10_2_pct: number;
  hnd_a20_1_pct: number;
  hnd_a20_x_pct: number;
  hnd_a20_2_pct: number;
  // MS + 1.5
  ms1_alt15_pct: number;
  ms1_ust15_pct: number;
  msx_alt15_pct: number;
  msx_ust15_pct: number;
  ms2_alt15_pct: number;
  ms2_ust15_pct: number;
  // MS + KG
  ms1_kg_var_pct: number;
  ms1_kg_yok_pct: number;
  msx_kg_var_pct: number;
  msx_kg_yok_pct: number;
  ms2_kg_var_pct: number;
  ms2_kg_yok_pct: number;
  // Skor sıklığı
  score_freq: Record<string, number>;
  // HT alt-istatistikler (FT pattern'de dolu)
  ht_result_1_pct: number;
  ht_result_x_pct: number;
  ht_result_2_pct: number;
  ht_dc_1x_pct: number;
  ht_dc_x2_pct: number;
  ht_dc_12_pct: number;
  ht_alt_15_pct: number;
  ht_ust_15_pct: number;
  ht_kg_var_pct: number;
  ht_kg_yok_pct: number;
  // H2 alt-istatistikler (FT pattern'de dolu)
  h2_result_1_pct: number;
  h2_result_x_pct: number;
  h2_result_2_pct: number;
}

export interface AnalyzeResponse {
  match_id: string;
  home_team: string;
  away_team: string;
  league_code: string;
  season: string;
  ht: PeriodOut;
  half2: PeriodOut;
  ft: PeriodOut;
  ht_b: PatternResult | null;
  ht_c: PatternResult | null;
  h2_b: PatternResult | null;
  h2_c: PatternResult | null;
  ft_b: PatternResult | null;
  ft_c: PatternResult | null;
  skipped: boolean;
  skip_reason: string | null;
}

export interface MatchSummary {
  match_id: string;
  home_team: string;
  away_team: string;
  league_code: string | null;
  season: string | null;
  actual_ft_home: number | null;
  actual_ft_away: number | null;
  actual_ht_home: number | null;
  actual_ht_away: number | null;
  ft_scores_1: string[] | null;
  ft_scores_x: string[] | null;
  ft_scores_2: string[] | null;
}
