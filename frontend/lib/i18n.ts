import trDict from "../dictionaries/tr.json";
import enDict from "../dictionaries/en.json";

export type Locale = "tr" | "en";
export const defaultLocale: Locale = "tr";
export const locales: Locale[] = ["tr", "en"];
export const COOKIE_NAME = "nv_lang";

export type Dictionary = typeof trDict;

const dictionaries: Record<Locale, Dictionary> = { tr: trDict, en: enDict };

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale] ?? dictionaries[defaultLocale];
}

export function isLocale(v: unknown): v is Locale {
  return v === "tr" || v === "en";
}
