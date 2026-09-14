import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiBase, getProxyTarget } from "@/lib/env";

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

describe("API URL resolution", () => {
  it("uses an absolute local URL during SSR", () => {
    vi.stubGlobal("window", undefined);
    vi.stubEnv("BACKEND_URL", ""); vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    expect(getApiBase()).toBe("http://localhost:8000");
  });
  it("uses same-origin proxy in browser and keeps private URL private", () => {
    vi.stubEnv("BACKEND_URL", "https://private.example"); vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    expect(getApiBase()).toBe("");
  });
  it("normalizes public URL for browser and proxy", () => {
    vi.stubEnv("BACKEND_URL", ""); vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example///");
    expect(getApiBase()).toBe("https://api.example");
    expect(getProxyTarget()).toBe("https://api.example");
  });
});
