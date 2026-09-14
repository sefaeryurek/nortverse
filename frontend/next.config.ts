import type { NextConfig } from "next";
import { getProxyTarget } from "./lib/env";

const nextConfig: NextConfig = {
  turbopack: { root: __dirname },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${getProxyTarget()}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
