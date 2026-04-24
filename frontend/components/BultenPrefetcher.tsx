"use client";

interface Props {
  matchIds: string[];
}

// Geçici olarak devre dışı: backend Playwright fırtınasını önlemek için.
// Kullanıcı maça tıkladığında foreground tam analiz tetiklenir; prefetch yarış üretiyor.
export default function BultenPrefetcher(_: Props) {
  return null;
}
