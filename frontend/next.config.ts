import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",   // Required for Docker production build
  reactStrictMode: true,

  async rewrites() {
    // Proxy /api/* to Django in development so the frontend
    // doesn't need to handle CORS during local dev
    return process.env.NODE_ENV === "development"
      ? [
          {
            source: "/api/:path*",
            destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`,
          },
        ]
      : [];
  },
};

export default nextConfig;
