import { expect, it } from "vitest";
import { getRollingDates } from "@/components/DayTabs";

it("uses Istanbul weekday after UTC midnight boundary", () => {
  const days = getRollingDates(new Date("2026-09-13T22:30:00Z"));
  expect(days[1]).toEqual({ date: "2026-09-14", label: "Pzt", today: true });
  expect(new Set(days.map((d) => d.date)).size).toBe(8);
});

it("keeps today's result visible as yesterday after midnight", () => {
  const days = getRollingDates(new Date("2026-09-22T21:01:00Z"), undefined, "past");
  expect(days[0].date).toBe("2026-09-23");
  expect(days[1].date).toBe("2026-09-22");
  expect(days[7].date).toBe("2026-09-16");
});
