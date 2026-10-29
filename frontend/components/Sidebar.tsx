"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { useLocale } from "@/lib/locale-context";
import { logoutAndLeave } from "@/lib/logout";
import { setShadowEnabled, shadowEnabledInBrowser } from "@/lib/shadow";

const noopSubscribe = () => () => {};

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
    href: "/kupondas",
    key: "coupons" as const,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 5h16v4a2 2 0 000 4v4H4v-4a2 2 0 000-4V5z" />
        <path d="M10 5v12" strokeDasharray="2 2" />
      </svg>
    ),
  },
  {
    href: "/iy",
    key: "firstHalf" as const,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 3v18" />
        <path d="M12 3a9 9 0 010 18" fill="currentColor" fillOpacity="0.25" stroke="none" />
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

// Mobil alt çubukta doğrudan görünen sayfalar (gerisi "Daha fazla" panelinde)
const MOBILE_PRIMARY = ["/bulten", "/canli", "/iy", "/kupondas"];

export default function Sidebar() {
  const pathname = usePathname();
  const { locale, t, setLocale } = useLocale();
  // Gölge lig tercihi çerezden (sunucuda kapalı sayılır → hidrasyon uyuşur); değişince sayfa yenilenir
  const shadowOn = useSyncExternalStore(noopSubscribe, shadowEnabledInBrowser, () => false);
  // Kayıtlı tercih depodan okunur (SSR'da kapalı); kullanıcı değiştirince override + kayıt.
  const savedExpanded = useSyncExternalStore(subscribeSidebar, readSidebar, () => false);
  const [override, setOverride] = useState<boolean | null>(null);
  const [moreOpen, setMoreOpen] = useState(false);
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
  const shortLabels: Partial<Record<string, string>> = { firstHalf: t.nav.firstHalfShort, evaluation: t.nav.evaluationShort };
  const mobileItems = navItems.map((item) => ({ ...item, shortLabel: shortLabels[item.key] ?? item.label }));
  const mobilePrimary = MOBILE_PRIMARY.map((href) => mobileItems.find((i) => i.href === href)).filter((i) => i !== undefined);
  const mobileExtra = mobileItems.filter((i) => !MOBILE_PRIMARY.includes(i.href));

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
          <button
            onClick={() => void logoutAndLeave()}
            className="flex items-center gap-3 rounded-lg transition-all"
            style={{
              padding: expanded ? "8px 12px" : "8px 0",
              justifyContent: expanded ? "flex-start" : "center",
              color: "var(--nv-text-tertiary)",
              transitionDuration: "var(--nv-duration-normal)",
            }}
            title={expanded ? undefined : t.auth.logout}
            aria-label={t.auth.logout}
          >
            <span className="flex-shrink-0 flex items-center justify-center text-xs font-bold" style={{ width: 20, height: 20 }} aria-hidden="true">
              ⎋
            </span>
            {expanded && <span className="text-sm font-medium truncate">{t.auth.logout}</span>}
          </button>
          <button
            onClick={() => setShadowEnabled(!shadowOn)}
            className="flex items-center gap-3 rounded-lg transition-all"
            style={{
              padding: expanded ? "8px 12px" : "8px 0",
              justifyContent: expanded ? "flex-start" : "center",
              color: shadowOn ? "var(--nv-accent-amber)" : "var(--nv-text-tertiary)",
              transitionDuration: "var(--nv-duration-normal)",
            }}
            title={t.nav.shadowHint}
            aria-pressed={shadowOn}
            aria-label={shadowOn ? t.nav.shadowHide : t.nav.shadowShow}
          >
            <span className="flex-shrink-0 flex items-center justify-center text-xs font-bold" style={{ width: 20, height: 20 }} aria-hidden="true">
              {shadowOn ? "◉" : "○"}
            </span>
            {expanded && (
              <span className="text-sm font-medium truncate">
                {shadowOn ? t.nav.shadowHide : t.nav.shadowShow}
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
      {/* Sprint 94 L3: 4 ana sayfa + "Daha fazla" (Sonuçlar, Değerlendirme, dil, gölge ligler, çıkış — mobilde yoktu) */}
      {moreOpen && (
        <div className="md:hidden fixed inset-0" style={{ zIndex: 44, backgroundColor: "var(--nv-bg-overlay)" }}
          onClick={() => setMoreOpen(false)} aria-hidden="true" />
      )}
      {moreOpen && (
        <div id="nv-mobile-more" role="menu" aria-label={t.nav.more}
          className="md:hidden fixed left-0 right-0 flex flex-col gap-1 p-2 nv-glass"
          style={{ bottom: "var(--nv-bottom-bar-h)", zIndex: 46, borderTop: "1px solid var(--nv-border)" }}>
          {mobileExtra.map(({ href, label, icon }) => (
            <Link key={href} href={href} role="menuitem" onClick={() => setMoreOpen(false)}
              aria-current={pathname === href || pathname.startsWith(href + "/") ? "page" : undefined}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5" style={{ color: "var(--nv-text-secondary)" }}>
              <span className="flex items-center justify-center" style={{ width: 20, height: 20 }}>{icon}</span>
              <span className="text-sm font-medium">{label}</span>
            </Link>
          ))}
          <button role="menuitem" onClick={() => setLocale(locale === "tr" ? "en" : "tr")}
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-left" style={{ color: "var(--nv-text-secondary)" }}>
            <span className="flex items-center justify-center text-xs font-bold" style={{ width: 20, height: 20 }}>{locale === "tr" ? "EN" : "TR"}</span>
            <span className="text-sm font-medium">{locale === "tr" ? "English" : "Türkçe"}</span>
          </button>
          <button role="menuitemcheckbox" aria-checked={shadowOn} onClick={() => setShadowEnabled(!shadowOn)}
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-left"
            style={{ color: shadowOn ? "var(--nv-accent-amber)" : "var(--nv-text-secondary)" }}>
            <span className="flex items-center justify-center text-xs font-bold" style={{ width: 20, height: 20 }} aria-hidden="true">{shadowOn ? "◉" : "○"}</span>
            <span className="text-sm font-medium">{shadowOn ? t.nav.shadowHide : t.nav.shadowShow}</span>
          </button>
          <button role="menuitem" onClick={() => void logoutAndLeave()}
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-left" style={{ color: "var(--nv-text-secondary)" }}>
            <span className="flex items-center justify-center text-xs font-bold" style={{ width: 20, height: 20 }} aria-hidden="true">⎋</span>
            <span className="text-sm font-medium">{t.auth.logout}</span>
          </button>
        </div>
      )}
      <nav
        aria-label={locale === "tr" ? "Mobil ana menü" : "Mobile main menu"}
        className="md:hidden fixed bottom-0 left-0 right-0 flex items-stretch nv-glass"
        style={{
          height: "var(--nv-bottom-bar-h)",
          zIndex: 47,
          borderTop: "1px solid var(--nv-border)",
        }}
      >
        {mobilePrimary.map(({ href, label, shortLabel, icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              aria-label={label}
              className="flex-1 min-w-0 flex flex-col items-center justify-center gap-1 transition-colors"
              style={{
                color: active ? "var(--nv-accent-blue)" : "var(--nv-text-tertiary)",
                transitionDuration: "var(--nv-duration-fast)",
              }}
            >
              <span className="flex items-center justify-center" style={{ width: 20, height: 20 }}>
                {icon}
              </span>
              <span className="font-medium truncate max-w-full px-0.5" style={{ fontSize: "var(--nv-text-2xs)" }} aria-hidden="true">
                {shortLabel}
              </span>
            </Link>
          );
        })}
        <button
          type="button"
          onClick={() => setMoreOpen((v) => !v)}
          aria-expanded={moreOpen}
          aria-controls="nv-mobile-more"
          aria-label={t.nav.more}
          className="flex-1 min-w-0 flex flex-col items-center justify-center gap-1"
          style={{ color: moreOpen || mobileExtra.some(({ href }) => pathname.startsWith(href)) ? "var(--nv-accent-blue)" : "var(--nv-text-tertiary)" }}
        >
          <span className="flex items-center justify-center text-base font-bold" style={{ width: 20, height: 20 }} aria-hidden="true">⋯</span>
          <span className="font-medium truncate" style={{ fontSize: "var(--nv-text-2xs)" }} aria-hidden="true">{t.nav.moreShort}</span>
        </button>
      </nav>
    </>
  );
}
