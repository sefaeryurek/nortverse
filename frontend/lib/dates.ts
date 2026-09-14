export function isCalendarDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith("0000")) return false;
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

export function resolvePageDate(value: string | string[] | undefined, today: string, fixture = false): string | null {
  if (value === undefined) return today;
  if (!isCalendarDate(value)) return null;
  if (fixture) {
    const days = (Date.parse(`${value}T12:00:00Z`) - Date.parse(`${today}T12:00:00Z`)) / 86400000;
    if (days < -30 || days > 14) return null;
  }
  return value;
}
