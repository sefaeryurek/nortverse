/**
 * Lig adı → bayrak + kısa kod eşleştirmesi.
 * Backend `league_code` artık tam ad döndürüyor (örn "English Premier League"),
 * eski "ENG PR" kısa kodları yok.
 */

export interface LeagueDisplay {
  flag: string;
  short: string;
}

const LEAGUES: Record<string, LeagueDisplay> = {
  // Avrupa
  "English Premier League": { flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", short: "ENG" },
  "English Championship": { flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", short: "ENG2" },
  "English League One": { flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", short: "ENG3" },
  "Spanish La Liga": { flag: "🇪🇸", short: "ESP" },
  "Spanish La Liga 2": { flag: "🇪🇸", short: "ESP2" },
  "Spanish Segunda Division": { flag: "🇪🇸", short: "ESP2" },
  "Italy Serie A": { flag: "🇮🇹", short: "ITA" },
  "Italian Serie A": { flag: "🇮🇹", short: "ITA" },
  "Italy Serie B": { flag: "🇮🇹", short: "ITA2" },
  "German Bundesliga": { flag: "🇩🇪", short: "GER" },
  "German Bundesliga 2": { flag: "🇩🇪", short: "GER2" },
  "French Ligue 1": { flag: "🇫🇷", short: "FRA" },
  "French Ligue 2": { flag: "🇫🇷", short: "FRA2" },
  "Portuguese Primeira Liga": { flag: "🇵🇹", short: "POR" },
  "Netherlands Eredivisie": { flag: "🇳🇱", short: "NED" },
  "Dutch Eredivisie": { flag: "🇳🇱", short: "NED" },
  "Turkish Super League": { flag: "🇹🇷", short: "TUR" },
  "Turkey Super League": { flag: "🇹🇷", short: "TUR" },
  "Belgian Pro League": { flag: "🇧🇪", short: "BEL" },
  "Scottish Premiership": { flag: "🏴󠁧󠁢󠁳󠁣󠁴󠁿", short: "SCO" },
  "Greek Super League": { flag: "🇬🇷", short: "GRE" },
  "Russian Premier League": { flag: "🇷🇺", short: "RUS" },
  "Austrian Bundesliga": { flag: "🇦🇹", short: "AUT" },
  "Swiss Super League": { flag: "🇨🇭", short: "SUI" },
  "Polish Ekstraklasa": { flag: "🇵🇱", short: "POL" },
  "Czech First League": { flag: "🇨🇿", short: "CZE" },
  "Danish Superliga": { flag: "🇩🇰", short: "DEN" },
  "Norwegian Eliteserien": { flag: "🇳🇴", short: "NOR" },
  "Swedish Allsvenskan": { flag: "🇸🇪", short: "SWE" },

  // UEFA
  "UEFA Champions League": { flag: "🏆", short: "UCL" },
  "UEFA Europa League": { flag: "🏆", short: "UEL" },
  "UEFA Conference League": { flag: "🏆", short: "UECL" },
  "UEFA Nations League": { flag: "🇪🇺", short: "UNL" },

  // Amerika
  "USA MLS": { flag: "🇺🇸", short: "MLS" },
  "Major League Soccer": { flag: "🇺🇸", short: "MLS" },
  "Brazilian Serie A": { flag: "🇧🇷", short: "BRA" },
  "Brazil Serie A": { flag: "🇧🇷", short: "BRA" },
  "Argentinian Primera Division": { flag: "🇦🇷", short: "ARG" },
  "Argentina Primera Division": { flag: "🇦🇷", short: "ARG" },
  "Mexican Liga MX": { flag: "🇲🇽", short: "MEX" },

  // Asya / Diğer
  "Saudi Pro League": { flag: "🇸🇦", short: "KSA" },
  "Japanese J1 League": { flag: "🇯🇵", short: "JPN" },
  "Korean K League 1": { flag: "🇰🇷", short: "KOR" },
  "Australian A-League": { flag: "🇦🇺", short: "AUS" },
};

const FALLBACK: LeagueDisplay = { flag: "⚽", short: "—" };

export function leagueDisplay(code: string | null | undefined, name?: string | null): LeagueDisplay {
  if (!code && !name) return FALLBACK;
  // Hem code hem name dene — code öncelikli
  return LEAGUES[code ?? ""] ?? LEAGUES[name ?? ""] ?? FALLBACK;
}
