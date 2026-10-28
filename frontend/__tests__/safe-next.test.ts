import { describe, expect, it } from "vitest";
import { DEFAULT_NEXT, safeNext } from "@/lib/safe-next";

const ORIGIN = "https://nortverse.example.ts.net";
// ?next= değeri URLSearchParams ile çözülmüş haliyle gelir — saldırılar da çözülmüş haliyle denenir
const decoded = (query: string) => new URLSearchParams(query).get("next");

describe("safeNext", () => {
  it("rejects encoded open-redirect tricks", () => {
    expect(safeNext(decoded("next=/%5Cevil.com"), ORIGIN)).toBe(DEFAULT_NEXT);
    expect(safeNext(decoded("next=/%09/evil.com"), ORIGIN)).toBe(DEFAULT_NEXT);
    expect(safeNext(decoded("next=/%0A/evil.com"), ORIGIN)).toBe(DEFAULT_NEXT);
    expect(safeNext("//evil.com", ORIGIN)).toBe(DEFAULT_NEXT);
    expect(safeNext("https://evil.com", ORIGIN)).toBe(DEFAULT_NEXT);
    expect(safeNext("/\\/evil.com", ORIGIN)).toBe(DEFAULT_NEXT);
  });

  it("keeps same-site paths with query and hash", () => {
    expect(safeNext("/kupondas", ORIGIN)).toBe("/kupondas");
    expect(safeNext(decoded("next=%2Fbulten%3Fdate%3D2026-10-28"), ORIGIN)).toBe("/bulten?date=2026-10-28");
    expect(safeNext("/analyze/2813084?home=A&away=B#ms", ORIGIN)).toBe("/analyze/2813084?home=A&away=B#ms");
  });

  it("falls back for empty values and the login page itself", () => {
    expect(safeNext(null, ORIGIN)).toBe(DEFAULT_NEXT);
    expect(safeNext("", ORIGIN)).toBe(DEFAULT_NEXT);
    expect(safeNext("bulten", ORIGIN)).toBe(DEFAULT_NEXT);
    expect(safeNext("/giris?next=/bulten", ORIGIN)).toBe(DEFAULT_NEXT);
  });
});
