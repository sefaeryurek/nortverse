"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { useLocale } from "@/lib/locale-context";

const NAV_ICONS = [
  {
    href: "/bulten",
    key: "bulletin" as const,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M3 9h18M9 21V9" />
      </svg>
    ),
  },
  {
    href: "/sonuclar",
    key: "results" as const,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
      </svg>
    ),
  },
  {
    href: "/degerlendirme",
    key: "evaluation" as const,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
      </svg>
    ),
  },
  {
    href: "/canli",
    key: "live" as const,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" fill="var(--nv-accent-red)" stroke="none" />
        <circle cx="12" cy="12" r="7" />
        <circle cx="12" cy="12" r="11" />
      </svg>
    ),
  },
];

function subscribeSidebar(listener: () => void) {
  window.addEventListener("storage", listener);
  return () => window.removeEventListener("storage", listener);
}

function readSidebar(): boolean {
  try { return localStorage.getItem("nv_sidebar") === "1"; } catch { return false; }
}

export default function Sidebar() {
  const pathname = usePathname();
  const { locale, t, setLocale } = useLocale();
  // Kayıtlı tercih depodan okunur (SSR'da kapalı); kullanıcı değiştirince override + kayıt.
  const savedExpanded = useSyncExternalStore(subscribeSidebar, readSidebar, () => false);
  const [override, setOverride] = useState<boolean | null>(null);
  const expanded = override ?? savedExpanded;
  const setExpanded = (update: boolean | ((prev: boolean) => boolean)) => {
    const next = typeof update === "function" ? update(expanded) : update;
    setOverride(next);
    try { localStorage.setItem("nv_sidebar", next ? "1" : "0"); } catch { /* ignore */ }
  };

  const navItems = NAV_ICONS.map((item) => ({
    ...item,
    label: t.nav[item.key],
  }));

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
            aria-label={expanded ? t.nav.collapse : t.nav.expand}
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
        <nav aria-label={locale === "tr" ? "Ana menü" : "Main menu"} className="flex-1 flex flex-col gap-1 px-2 py-3">
          {navItems.map(({ href, label, icon }) => {
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
                aria-label={expanded ? undefined : label}
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

        {/* Language switcher + Footer */}
        <div
          className="flex flex-col gap-2 px-2 py-3"
          style={{ borderTop: "1px solid var(--nv-border)" }}
        >
          <button
            onClick={() => setLocale(locale === "tr" ? "en" : "tr")}
            className="flex items-center gap-3 rounded-lg transition-all"
            style={{
              padding: expanded ? "8px 12px" : "8px 0",
              justifyContent: expanded ? "flex-start" : "center",
              color: "var(--nv-text-tertiary)",
              transitionDuration: "var(--nv-duration-normal)",
            }}
            title={expanded ? undefined : t.nav.language}
            aria-label={t.nav.language}
          >
            <span className="flex-shrink-0 flex items-center justify-center text-xs font-bold" style={{ width: 20, height: 20 }}>
              {locale === "tr" ? "EN" : "TR"}
            </span>
            {expanded && (
              <span className="text-sm font-medium truncate">
                {locale === "tr" ? "English" : "Türkçe"}
              </span>
            )}
          </button>
          {expanded && (
            <div className="px-2 text-xs" style={{ color: "var(--nv-text-tertiary)" }}>
              {t.nav.footer}
            </div>
          )}
        </div>
      </aside>

      {/* ==================== MOBILE BOTTOM TAB BAR ==================== */}
      <nav
        aria-label={locale === "tr" ? "Mobil ana menü" : "Mobile main menu"}
        className="md:hidden fixed bottom-0 left-0 right-0 flex items-stretch nv-glass"
        style={{
          height: "var(--nv-bottom-bar-h)",
          zIndex: 40,
          borderTop: "1px solid var(--nv-border)",
        }}
      >
        {navItems.map(({ href, label, icon }) => {
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
