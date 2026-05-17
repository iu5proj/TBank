import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /** Standalone output for Docker deployment */
  output: "standalone",
  devIndicators: false,

  /**
   * Proxy API requests to the FastAPI backend during development.
   * In production, nginx handles this (see nginx.frontend.conf).
   *
   * This means the frontend can use either:
   *   - NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1  (direct, CORS required)
   *   - NEXT_PUBLIC_API_URL=/api/v1                       (proxied, no CORS issues)
   */
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
      {
        source: "/health",
        destination: "http://localhost:8000/health",
      },
    ];
  },

  /** Allow backend's OpenAPI docs endpoint in images if needed */
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
      },
    ],
  },
};

export default nextConfig;
