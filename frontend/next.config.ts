import type { NextConfig } from "next";

// The FastAPI backend. Same-origin /api/* requests are proxied there so the
// browser never needs CORS and the API key stays on the backend.
const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

// Dev only: hosts allowed to load hot-reload resources when the app is opened
// by IP instead of localhost. Extend with ALLOWED_DEV_ORIGINS=host1,host2.
const allowedDevOrigins = [
  "45.61.61.148",
  ...(process.env.ALLOWED_DEV_ORIGINS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
];

const nextConfig: NextConfig = {
  allowedDevOrigins,
  cacheComponents: true,
  partialPrefetching: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
