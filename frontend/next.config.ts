import type { NextConfig } from "next";
import { getProxyTarget } from "./lib/env";

const nextConfig: NextConfig = {
  turbopack: { root: __dirname },
  // Üretim sunucusu iki yuvadan birini kullanır (.next-prod-a / .next-prod-b, Sprint 94 E6): derleme boştaki
  // yuvaya yapılır, başarısızsa çalışan sürüm etkilenmez. Geliştirme modu varsayılan .next'te kalır.
  // Arkadaş artık üretim sunucusuna gelir; geliştirme sunucusu sadece bu bilgisayardan (allowedDevOrigins yok).
  distDir: process.env.NEXT_DIST_DIR || ".next",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${getProxyTarget()}/api/:path*`,
      },
      {
        source: "/ws/:path*",
        destination: `${getProxyTarget()}/ws/:path*`,
      },
    ];
  },
};

export default nextConfig;
