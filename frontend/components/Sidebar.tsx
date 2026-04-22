"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/bulten", label: "Bülten", icon: "📋" },
  { href: "/tahmin-1", label: "Tahmin (A1)", icon: "🎯" },
  { href: "/tahmin-2", label: "Tahmin (A2)", icon: "🔮" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="w-64 flex-shrink-0 flex flex-col border-r"
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
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ href, label, icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
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
        v0.5.0
      </div>
    </aside>
  );
}
