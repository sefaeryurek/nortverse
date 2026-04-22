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
  kg_var_pct: number;
  over_25_pct: number;
  result_1_pct: number;
  result_x_pct: number;
  result_2_pct: number;
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
  pattern_b: PatternResult | null;
  pattern_c: PatternResult | null;
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
