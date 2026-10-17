"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  type Dictionary,
  type Locale,
  COOKIE_NAME,
  defaultLocale,
  getDictionary,
} from "./i18n";

interface LocaleContextValue {
  locale: Locale;
  t: Dictionary;
  setLocale: (l: Locale) => void;
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: defaultLocale,
  t: getDictionary(defaultLocale),
  setLocale: () => {},
});

export function LocaleProvider({
  initial,
  children,
}: {
  initial: Locale;
  children: ReactNode;
}) {
  const [locale, setLocaleState] = useState<Locale>(initial);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    document.cookie = `${COOKIE_NAME}=${l};path=/;max-age=${60 * 60 * 24 * 365};samesite=lax`;
    window.location.reload();
  }, []);

  const value = useMemo(
    () => ({ locale, t: getDictionary(locale), setLocale }),
    [locale, setLocale],
  );

  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale() {
  return useContext(LocaleContext);
}
