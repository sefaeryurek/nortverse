import { expect, it, describe, vi, afterEach } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import RetryButton from "@/components/RetryButton";

const refreshMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: refreshMock }),
}));

afterEach(() => { cleanup(); refreshMock.mockClear(); });

describe("RetryButton", () => {
  it("renders with 'Tekrar dene' text", () => {
    render(<RetryButton />);
    expect(screen.getByText("Tekrar dene")).toBeDefined();
  });

  it("is a button element", () => {
    render(<RetryButton />);
    expect(screen.getByRole("button")).toBeDefined();
  });

  it("calls router.refresh on click", () => {
    render(<RetryButton />);
    fireEvent.click(screen.getByText("Tekrar dene"));
    expect(refreshMock).toHaveBeenCalledTimes(1);
  });

  it("has blue background style", () => {
    render(<RetryButton />);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-blue-600");
  });
});
