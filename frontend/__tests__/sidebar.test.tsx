import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import Sidebar from "@/components/Sidebar";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [k: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/bulten"),
}));

describe("Sidebar", () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    cleanup();
  });

  it("renders navigation links for all 4 pages", () => {
    render(<Sidebar />);
    const links = screen.getAllByRole("link");
    const navHrefs = links.map((l) => l.getAttribute("href")).filter(Boolean);
    expect(navHrefs).toEqual(expect.arrayContaining(["/bulten", "/sonuclar", "/degerlendirme", "/canli"]));
  });

  it("renders NV logo", () => {
    render(<Sidebar />);
    const nvElements = screen.getAllByText("NV");
    expect(nvElements.length).toBeGreaterThanOrEqual(1);
  });

  it("has toggle button with aria-label", () => {
    render(<Sidebar />);
    const toggleBtns = screen.getAllByLabelText(/menüyü/i);
    expect(toggleBtns.length).toBeGreaterThanOrEqual(1);
  });

  it("toggles expanded state and persists to localStorage", () => {
    render(<Sidebar />);
    const toggleBtn = screen.getAllByLabelText(/menüyü/i)[0];
    fireEvent.click(toggleBtn);
    expect(localStorage.getItem("nv_sidebar")).toBe("1");
    fireEvent.click(toggleBtn);
    expect(localStorage.getItem("nv_sidebar")).toBe("0");
  });

  it("shows NORTVERSE text when expanded", () => {
    localStorage.setItem("nv_sidebar", "1");
    render(<Sidebar />);
    expect(screen.getByText("NORTVERSE")).toBeTruthy();
  });

  it("hides NORTVERSE text when collapsed", () => {
    localStorage.setItem("nv_sidebar", "0");
    render(<Sidebar />);
    expect(screen.queryByText("NORTVERSE")).toBeNull();
  });

  it("shows footer text when expanded", () => {
    localStorage.setItem("nv_sidebar", "1");
    render(<Sidebar />);
    const footers = screen.getAllByText("Futbol Analiz Sistemi");
    expect(footers.length).toBeGreaterThanOrEqual(1);
  });

  it("marks active page with aria-current", () => {
    render(<Sidebar />);
    const activeLinks = screen.getAllByRole("link").filter(
      (l) => l.getAttribute("aria-current") === "page"
    );
    expect(activeLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("includes Canlı nav item", () => {
    localStorage.setItem("nv_sidebar", "1");
    render(<Sidebar />);
    expect(screen.getAllByText("Canlı").length).toBeGreaterThanOrEqual(1);
  });

  it("has desktop and mobile navigation sections", () => {
    render(<Sidebar />);
    const navs = screen.getAllByRole("navigation");
    expect(navs.length).toBeGreaterThanOrEqual(2);
  });
});
