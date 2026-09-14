import { expect, it } from "vitest";
import { isCalendarDate, resolvePageDate } from "@/lib/dates";
import { getRollingDates } from "@/components/DayTabs";

it.each(["2026-02-29", "2026-04-31", "2026-1-01", "0000-01-01", "", ["2026-01-01", "2026-01-02"]])(
  "rejects invalid or ambiguous dates %s", (value) => expect(isCalendarDate(value)).toBe(false),
);
it("accepts leap days only in leap years", () => expect(isCalendarDate("2024-02-29")).toBe(true));
it("applies fixture date bounds without restricting result archives", () => {
  expect(resolvePageDate(undefined, "2026-09-14", true)).toBe("2026-09-14");
  expect(resolvePageDate("2026-08-15", "2026-09-14", true)).toBe("2026-08-15");
  expect(resolvePageDate("2026-08-14", "2026-09-14", true)).toBeNull();
  expect(resolvePageDate("2026-09-28", "2026-09-14", true)).toBe("2026-09-28");
  expect(resolvePageDate("2026-09-29", "2026-09-14", true)).toBeNull();
  expect(resolvePageDate("2020-01-01", "2026-09-14")).toBe("2020-01-01");
});
it("keeps the server calendar during hydration across midnight", () => {
  expect(getRollingDates(new Date("2026-09-14T22:00:00Z"), "2026-09-14")[1].date).toBe("2026-09-14");
});
