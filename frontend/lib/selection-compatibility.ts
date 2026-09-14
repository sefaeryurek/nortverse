// A concrete score is evidence of compatibility, never of independence.
// Unsupported markets fail closed for automatic combo generation.
type Score = { home: number; away: number; htHome: number; htAway: number };
type Predicate = (score: Score) => boolean;
const result = (home: number, away: number) => home > away ? "1" : home < away ? "2" : "x";

function predicate(field: string): Predicate | null {
  let m: RegExpMatchArray | null;
  if ((m = field.match(/^(ht_|h2_)?result_([1x2])_pct$/))) {
    const [, period, selection] = m;
    return (s) => result(...goals(s, period)) === selection;
  }
  if ((m = field.match(/^(ht_)?dc_(1x|x2|12)_pct$/))) {
    const [, period, selection] = m;
    return (s) => selection.includes(result(...goals(s, period)));
  }
  if ((m = field.match(/^(ht_|h2_)?kg_(var|yok)_pct$/))) {
    const [, period, selection] = m;
    return (s) => {
      const [h, a] = goals(s, period);
      return (h > 0 && a > 0) === (selection === "var");
    };
  }
  if ((m = field.match(/^(ev_|dep_|iy_|ht_)?(alt|ust)_(05|15|25|35)_pct$/))) {
    const [, side, direction, limit] = m;
    return (s) => {
      const total = side === "ev_" ? s.home : side === "dep_" ? s.away
        : side === "iy_" || side === "ht_" ? s.htHome + s.htAway : s.home + s.away;
      return direction === "alt" ? total < Number(limit) / 10 : total > Number(limit) / 10;
    };
  }
  if ((m = field.match(/^ms([1x2])_(alt|ust)(15|25)_pct$/))) {
    const [, selection, direction, limit] = m;
    const total = predicate(`${direction}_${limit}_pct`)!;
    return (s) => result(s.home, s.away) === selection && total(s);
  }
  if ((m = field.match(/^ms([1x2])_kg_(var|yok)_pct$/))) {
    const [, selection, kg] = m;
    const both = predicate(`kg_${kg}_pct`)!;
    return (s) => result(s.home, s.away) === selection && both(s);
  }
  if ((m = field.match(/^iy_ms_([1x2])([1x2])_pct$/))) {
    const [, ht, ft] = m;
    return (s) => result(s.htHome, s.htAway) === ht && result(s.home, s.away) === ft;
  }
  if ((m = field.match(/^hnd_([ah])([12])0_([1x2])_pct$/))) {
    const [, side, amount, selection] = m;
    return (s) => result(s.home + (side === "h" ? Number(amount) : 0),
      s.away + (side === "a" ? Number(amount) : 0)) === selection;
  }
  if (field === "fark_ber_pct") return (s) => s.home === s.away;
  if ((m = field.match(/^fark_(ev|dep)(1|2|3p)_pct$/))) {
    const [, side, margin] = m;
    return (s) => {
      const diff = side === "ev" ? s.home - s.away : s.away - s.home;
      return margin === "3p" ? diff >= 3 : diff === Number(margin);
    };
  }
  if ((m = field.match(/^gol_(01|23|45|6p)_pct$/))) {
    const range = m[1];
    return (s) => range === "6p" ? s.home + s.away >= 6
      : s.home + s.away >= Number(range[0]) && s.home + s.away <= Number(range[1]);
  }
  return null;
}

function goals(s: Score, period?: string): [number, number] {
  if (period === "ht_") return [s.htHome, s.htAway];
  if (period === "h2_") return [s.home - s.htHome, s.away - s.htAway];
  return [s.home, s.away];
}

export function canCombineFields(fields: string[]): boolean {
  const predicates = fields.map(predicate);
  if (predicates.some((p) => p === null)) return false;
  // Bounded witness search: lack of a witness rejects the suggestion conservatively.
  // This is not a probability model or an exhaustive football score distribution.
  for (let home = 0; home <= 10; home++) {
    for (let away = 0; away <= 10; away++) {
      for (let htHome = 0; htHome <= home; htHome++) {
        for (let htAway = 0; htAway <= away; htAway++) {
          const score = { home, away, htHome, htAway };
          if (predicates.every((p) => p!(score))) return true;
        }
      }
    }
  }
  return false;
}
