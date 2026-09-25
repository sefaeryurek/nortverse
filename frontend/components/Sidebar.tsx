"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const NAV = [
  {
    href: "/bulten",
    label: "Bulten",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M3 9h18M9 21V9" />
      </svg>
    ),
  },
  {
    href: "/sonuclar",
    label: "Sonuclar",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      {/* ==================== DESKTOP SIDEBAR ==================== */}
      <aside
        className="hidden md:flex flex-col flex-shrink-0 h-full transition-all ease-[cubic-bezier(0.16,1,0.3,1)]"
        style={{
          width: expanded ? "var(--nv-sidebar-expanded)" : "var(--nv-sidebar-collapsed)",
          transitionDuration: "var(--nv-duration-slow)",
          backgroundColor: "var(--nv-bg-surface)",
          borderRight: "1px solid var(--nv-border)",
        }}
      >
        {/* Logo + Toggle */}
        <div
          className="flex items-center justify-between px-4 flex-shrink-0"
          style={{
            height: "var(--nv-header-h)",
            borderBottom: "1px solid var(--nv-border)",
          }}
        >
          <Link href="/bulten" className="flex items-center gap-2 min-w-0">
            <span
              className="flex-shrink-0 flex items-center justify-center rounded-lg font-bold text-sm"
              style={{
                width: 32,
                height: 32,
                background: "linear-gradient(135deg, var(--nv-accent-blue), var(--nv-accent-green))",
                color: "var(--nv-bg-base)",
              }}
            >
              NV
            </span>
            {expanded && (
              <span
                className="text-sm font-bold tracking-wide truncate"
                style={{ color: "var(--nv-text-primary)" }}
              >
                NORTVERSE
              </span>
            )}
          </Link>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex-shrink-0 flex items-center justify-center w-7 h-7 rounded-md transition-colors"
            style={{ color: "var(--nv-text-tertiary)" }}
            aria-label={expanded ? "Menüyü daralt" : "Menüyü genişlet"}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
                transition: `transform var(--nv-duration-slow) var(--nv-ease)`,
              }}
            >
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>
        </div>

        {/* Nav */}
        <nav aria-label="Ana menu" className="flex-1 flex flex-col gap-1 px-2 py-3">
          {NAV.map(({ href, label, icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className="flex items-center gap-3 rounded-lg transition-all"
                style={{
                  padding: expanded ? "10px 12px" : "10px 0",
                  justifyContent: expanded ? "flex-start" : "center",
                  backgroundColor: active ? "var(--nv-accent-blue-dim)" : "transparent",
                  color: active ? "var(--nv-accent-blue)" : "var(--nv-text-secondary)",
                  transitionDuration: "var(--nv-duration-normal)",
                  transitionTimingFunction: "var(--nv-ease)",
                }}
                title={expanded ? undefined : label}
              >
                <span className="flex-shrink-0 flex items-center justify-center" style={{ width: 20, height: 20 }}>
                  {icon}
                </span>
                {expanded && (
                  <span className="text-sm font-medium truncate">{label}</span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        {expanded && (
          <div
            className="px-4 py-3 text-xs"
            style={{
              borderTop: "1px solid var(--nv-border)",
              color: "var(--nv-text-tertiary)",
            }}
          >
            Futbol Analiz Sistemi
          </div>
        )}
      </aside>

      {/* ==================== MOBILE BOTTOM TAB BAR ==================== */}
      <nav
        aria-label="Mobil ana menu"
        className="md:hidden fixed bottom-0 left-0 right-0 flex items-stretch nv-glass"
        style={{
          height: "var(--nv-bottom-bar-h)",
          zIndex: 40,
          borderTop: "1px solid var(--nv-border)",
        }}
      >
        {NAV.map(({ href, label, icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className="flex-1 flex flex-col items-center justify-center gap-1 transition-colors"
              style={{
                color: active ? "var(--nv-accent-blue)" : "var(--nv-text-tertiary)",
                transitionDuration: "var(--nv-duration-fast)",
              }}
            >
              <span className="flex items-center justify-center" style={{ width: 20, height: 20 }}>
                {icon}
              </span>
              <span
                className="font-medium"
                style={{ fontSize: "var(--nv-text-xs)" }}
              >
                {label}
              </span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
