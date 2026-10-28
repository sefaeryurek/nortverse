import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import DayTabs from "@/components/DayTabs";
import { HtMatchList } from "@/components/HtBoard";
import { resolvePageDate } from "@/lib/dates";
import { type Locale, COOKIE_NAME, defaultLocale, getDictionary, isLocale } from "@/lib/i18n";
import { SHADOW_COOKIE, shadowFromCookie } from "@/lib/shadow";

export const metadata: Metadata = {
  title: "İY Oranları",
  description: "İlk yarı pazarları: oran ve ima ettiği olasılık",
};

interface Props {
  searchParams: Promise<{ date?: string | string[] }>;
}

export default async function IyPage({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
  const date = resolvePageDate(params.date, today, true);
  if (date === null) redirect("/iy");
  const cookieStore = await cookies();
  const raw = cookieStore.get(COOKIE_NAME)?.value;
  const locale: Locale = isLocale(raw) ? raw : defaultLocale;
  const shadow = shadowFromCookie(cookieStore.get(SHADOW_COOKIE)?.value);
  const t = getDictionary(locale);

  return (
    <div className="flex flex-col h-full pb-[60px] md:pb-0">
      <div className="px-[var(--nv-page-gutter)] py-5 flex-shrink-0" style={{ borderBottom: "1px solid var(--nv-border)" }}>
        <h1 className="font-bold" style={{ fontSize: "var(--nv-text-xl)", color: "var(--nv-text-primary)", letterSpacing: "var(--nv-tracking-tight)" }}>
          {t.ht.title}
        </h1>
        <p className="mt-1" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{t.ht.subtitle}</p>
        <p className="mt-2" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)", maxWidth: "65ch" }}>{t.ht.note}</p>
      </div>
      <DayTabs referenceDate={today} activeDate={date} basePath="/iy" locale={locale} />
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<p className="p-6" style={{ color: "var(--nv-text-tertiary)" }}>…</p>}>
          <HtMatchList date={date} locale={locale} shadow={shadow} />
        </Suspense>
      </div>
    </div>
  );
}
