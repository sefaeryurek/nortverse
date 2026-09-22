import { act, cleanup, render } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import AutoRefresh from "@/components/AutoRefresh";

const refresh = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); refresh.mockClear(); });

it("refreshes a recent match day as soon as a hidden tab becomes visible", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-22T08:00:00Z"));
  const visibility = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
  render(<AutoRefresh intervalMs={45_000} />);

  act(() => { document.dispatchEvent(new Event("visibilitychange")); });
  expect(refresh).not.toHaveBeenCalled();

  visibility.mockReturnValue("visible");
  act(() => { document.dispatchEvent(new Event("visibilitychange")); });
  expect(refresh).toHaveBeenCalledTimes(1);
  act(() => { window.dispatchEvent(new Event("focus")); });
  expect(refresh).toHaveBeenCalledTimes(1);
});
