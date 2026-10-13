import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import LiveMatchBadge from "@/components/LiveMatchBadge";
import { isLiveScoreStale } from "@/lib/score-freshness";

vi.mock("@/lib/score-freshness", () => ({
  isLiveScoreStale: vi.fn(() => false),
}));

describe("LiveMatchBadge", () => {
  beforeEach(() => {
    vi.mocked(isLiveScoreStale).mockReturnValue(false);
  });
  afterEach(() => {
    cleanup();
  });

  it("renders score as home - away", () => {
    render(
      <LiveMatchBadge home={2} away={1} minute="45" checkedAt={null} checkedLabel={null} initialStale={false} />
    );
    expect(screen.getByText("2 - 1")).toBeTruthy();
  });

  it("shows minute label with prime symbol", () => {
    render(
      <LiveMatchBadge home={1} away={0} minute="67" checkedAt={null} checkedLabel={null} initialStale={false} />
    );
    expect(screen.getByText("67′")).toBeTruthy();
  });

  it("shows HT as İY", () => {
    render(
      <LiveMatchBadge home={0} away={0} minute="HT" checkedAt={null} checkedLabel={null} initialStale={false} />
    );
    expect(screen.getByText("İY")).toBeTruthy();
  });

  it("shows CANLI when minute is null", () => {
    render(
      <LiveMatchBadge home={1} away={1} minute={null} checkedAt={null} checkedLabel={null} initialStale={false} />
    );
    expect(screen.getByText("CANLI")).toBeTruthy();
  });

  it("shows checked label when provided", () => {
    render(
      <LiveMatchBadge home={0} away={0} minute="30" checkedAt={null} checkedLabel="14:30" initialStale={false} />
    );
    expect(screen.getByText("Son kontrol 14:30")).toBeTruthy();
  });

  it("shows fallback when checkedLabel is null", () => {
    render(
      <LiveMatchBadge home={0} away={0} minute="30" checkedAt={null} checkedLabel={null} initialStale={false} />
    );
    expect(screen.getByText("Kontrol zamanı bilinmiyor")).toBeTruthy();
  });

  it("has aria-label for live score", () => {
    render(
      <LiveMatchBadge home={1} away={0} minute="45" checkedAt={null} checkedLabel={null} initialStale={false} />
    );
    expect(screen.getByLabelText("Canlı skor")).toBeTruthy();
  });

  it("has stale aria-label when stale", () => {
    vi.mocked(isLiveScoreStale).mockReturnValue(true);
    render(
      <LiveMatchBadge home={1} away={0} minute="45" checkedAt={null} checkedLabel={null} initialStale={true} />
    );
    expect(screen.getByLabelText("Son görülen skor; güncel veri bekleniyor")).toBeTruthy();
  });

  it("shows 'Son skor' text when stale", () => {
    vi.mocked(isLiveScoreStale).mockReturnValue(true);
    render(
      <LiveMatchBadge home={2} away={0} minute="60" checkedAt={null} checkedLabel={null} initialStale={true} />
    );
    expect(screen.getByText("Son skor")).toBeTruthy();
  });

  it("renders data-stale attribute as true when stale", () => {
    vi.mocked(isLiveScoreStale).mockReturnValue(true);
    const { container } = render(
      <LiveMatchBadge home={0} away={0} minute={null} checkedAt={null} checkedLabel={null} initialStale={true} />
    );
    const badge = container.querySelector("[data-stale]");
    expect(badge).toBeTruthy();
    expect(badge?.getAttribute("data-stale")).toBe("true");
  });
});
