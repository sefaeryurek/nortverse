import { describe, expect, it } from "vitest";
import { formatTime } from "@/lib/dates";

describe("formatTime", () => {
  it("returns --:-- for null", () => {
    expect(formatTime(null)).toBe("--:--");
  });

  it("returns --:-- for empty string", () => {
    expect(formatTime("")).toBe("--:--");
  });

  it("returns fallback for invalid ISO string", () => {
    const result = formatTime("not-a-date");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("formats a valid UTC ISO string to Istanbul time", () => {
    const result = formatTime("2026-10-11T15:00:00Z");
    expect(result).toMatch(/^\d{2}:\d{2}$/);
    expect(result).toBe("18:00");
  });

  it("formats midnight UTC to 03:00 Istanbul", () => {
    const result = formatTime("2026-10-11T00:00:00Z");
    expect(result).toBe("03:00");
  });

  it("handles ISO with timezone offset", () => {
    const result = formatTime("2026-10-11T20:00:00+03:00");
    expect(result).toBe("20:00");
  });
});
