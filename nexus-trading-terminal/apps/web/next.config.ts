import type { NextConfig } from "next";

// The browser only ever talks to this Next.js server. API calls are proxied
// server-side to FastAPI, so provider keys and the backend origin never reach
// the client bundle.
const API_URL = process.env.NEXUS_API_URL ?? "http://127.0.0.1:8000";
const isProd = process.env.NODE_ENV === "production";

const csp = [
  "default-src 'self'",
  "img-src 'self' data: blob:",
  "style-src 'self' 'unsafe-inline'",
  `script-src 'self' 'unsafe-inline'${isProd ? "" : " 'unsafe-eval'"}`,
  "font-src 'self' data:",
  "connect-src 'self' ws: wss: http://127.0.0.1:8000 http://localhost:8000",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Project guidance for coding agents lives in the repository root CLAUDE.md.
  agentRules: false,
  // `next dev` only serves its dev assets to the announced host (localhost) by default;
  // also allow 127.0.0.1 so both loopback URLs work in development.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // Self-contained server bundle for the Docker image; plain `next start` locally.
  output: process.env.NEXT_STANDALONE === "1" ? "standalone" : undefined,
  transpilePackages: ["@nexus/shared-types"],
  experimental: {
    proxyClientMaxBodySize: "25mb",
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/health", destination: `${API_URL}/health` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          ...(isProd ? [{ key: "Content-Security-Policy", value: csp }] : []),
        ],
      },
    ];
  },
};

export default nextConfig;
