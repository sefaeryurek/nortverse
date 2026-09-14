"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/bulten", label: "Bülten", icon: "📋" },
  { href: "/sonuclar", label: "Sonuçlar", icon: "✅" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <>
    <header className="flex items-center justify-between gap-3 border-b border-slate-700 bg-slate-900 px-4 py-3 md:hidden">
      <Link href="/bulten" className="text-sm font-bold tracking-wide text-blue-400">NORTVERSE</Link>
      <nav aria-label="Mobil ana menü" className="flex gap-1">
        {NAV.map(({ href, label }) => <Link key={href} href={href}
          aria-current={pathname === href ? "page" : undefined}
          className={`rounded-lg px-3 py-2 text-sm font-medium ${pathname === href ? "bg-blue-900 text-blue-100" : "text-slate-300 hover:bg-slate-800"}`}>
          {label}
        </Link>)}
      </nav>
    </header>
    <aside
      className="hidden md:flex w-64 flex-shrink-0 flex-col border-r"
      style={{ backgroundColor: "#161b27", borderColor: "#2d3748" }}
    >
      {/* Logo */}
      <div className="px-6 py-5 border-b" style={{ borderColor: "#2d3748" }}>
        <span className="text-xl font-bold tracking-wide" style={{ color: "#3b82f6" }}>
          NORTVERSE
        </span>
        <p className="text-xs mt-0.5" style={{ color: "#94a3b8" }}>
          Futbol Analiz Sistemi
        </p>
      </div>

      {/* Nav */}
      <nav aria-label="Ana menü" className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ href, label, icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors"
              style={{
                backgroundColor: active ? "#1e3a5f" : "transparent",
                color: active ? "#93c5fd" : "#94a3b8",
              }}
            >
              <span>{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-6 py-4 border-t text-xs" style={{ borderColor: "#2d3748", color: "#475569" }}>
        Futbol istatistikleri ve maç analizi
      </div>
    </aside>
    </>
  );
}
