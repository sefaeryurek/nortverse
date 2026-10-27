import type { NextConfig } from "next";
import { getProxyTarget } from "./lib/env";

const nextConfig: NextConfig = {
  turbopack: { root: __dirname },
  // Arkadaş siteye Tailscale serve üzerinden (https://<bilgisayar>.<ağ>.ts.net) gelir; geliştirme modu
  // başka adresten gelen istekleri varsayılan olarak engeller.
  allowedDevOrigins: ["*.ts.net"],
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
