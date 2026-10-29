import { afterEach, expect, it, vi } from "vitest";
import { readStorage, STORAGE_KEY, writeStorage } from "@/lib/cart";
import { logoutAndLeave } from "@/lib/logout";
import { makeCartItem } from "./fixtures";

// Sprint 94 E8: çıkışta sepet temizlenir, oturum kapatılır, giriş sayfasına gidilir
afterEach(() => { vi.restoreAllMocks(); window.localStorage.clear(); });

it("logs out, clears the bet cart and goes to /giris", async () => {
  writeStorage([makeCartItem()]);
  expect(readStorage().length).toBe(1);
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
  const go = vi.fn();
  await logoutAndLeave(go);
  expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", { method: "POST" });
  expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "null")).toEqual([]);
  expect(go).toHaveBeenCalledWith("/giris");
});

it("still clears and leaves when the server is unreachable", async () => {
  writeStorage([makeCartItem()]);
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ağ"));
  const go = vi.fn();
  await logoutAndLeave(go);
  expect(readStorage()).toEqual([]);
  expect(go).toHaveBeenCalledWith("/giris");
});
