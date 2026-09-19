import { expect, it, describe } from "vitest";
import { leagueDisplay } from "@/lib/leagues";

describe("leagueDisplay", () => {
  it("returns Turkish flag for Turkish Super League", () => {
    const d = leagueDisplay("Turkish Super League");
    expect(d.short).toBe("TUR");
  });

  it("returns English flag for English Premier League", () => {
    const d = leagueDisplay("English Premier League");
    expect(d.short).toBe("ENG");
  });

  it("returns fallback for unknown league", () => {
    const d = leagueDisplay("Unknown League");
    expect(d.flag).toBe("⚽");
    expect(d.short).toBe("Unknown Le…");
  });

  it("returns fallback for null code", () => {
    const d = leagueDisplay(null);
    expect(d.flag).toBe("⚽");
  });

  it("returns fallback for undefined code", () => {
    const d = leagueDisplay(undefined);
    expect(d.flag).toBe("⚽");
  });

  it("tries name when code is unknown", () => {
    const d = leagueDisplay("UNKNOWN_CODE", "German Bundesliga");
    expect(d.short).toBe("GER");
  });

  it("prefers code over name", () => {
    const d = leagueDisplay("French Ligue 1", "German Bundesliga");
    expect(d.short).toBe("FRA");
  });

  it("handles Italy alias", () => {
    const d1 = leagueDisplay("Italy Serie A");
    const d2 = leagueDisplay("Italian Serie A");
    expect(d1.short).toBe("ITA");
    expect(d2.short).toBe("ITA");
  });

  it("handles UEFA competitions", () => {
    expect(leagueDisplay("UEFA Champions League").short).toBe("UCL");
    expect(leagueDisplay("UEFA Europa League").short).toBe("UEL");
    expect(leagueDisplay("UEFA Conference League").short).toBe("UECL");
  });

  it("handles South American leagues", () => {
    expect(leagueDisplay("Brazilian Serie A").short).toBe("BRA");
    expect(leagueDisplay("Brazil Serie A").short).toBe("BRA");
    expect(leagueDisplay("Argentina Primera Division").short).toBe("ARG");
  });

  it("handles Asian leagues", () => {
    expect(leagueDisplay("Saudi Pro League").short).toBe("KSA");
    expect(leagueDisplay("Japanese J1 League").short).toBe("JPN");
  });

  it("recognizes fixture source league names", () => {
    expect(leagueDisplay("J2 League").short).toBe("JPN2");
    expect(leagueDisplay("England Championship").short).toBe("ENG2");
    expect(leagueDisplay("France Ligue 1").short).toBe("FRA");
    expect(leagueDisplay("Turkey Super Lig").short).toBe("TUR");
  });

  it("returns fallback when both code and name are null", () => {
    const d = leagueDisplay(null, null);
    expect(d.flag).toBe("⚽");
    expect(d.short).toBe("—");
  });
});
