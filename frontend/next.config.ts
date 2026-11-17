import type { NextConfig } from "next";

/**
 * Content-Security-Policy for production builds (the dev server needs eval for hot reload).
 * Everything is same-origin behind Caddy. Inline scripts and styles stay allowed: Next.js
 * bootstraps with inline scripts, and per-request nonces would turn off static and partial
 * prerendering. pdf.js runs its worker from our own origin (worker-src 'self').
 * API responses (including file downloads with their own sandbox CSP) are not served by Next.
 */
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "worker-src 'self' blob:",
  "frame-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const nextConfig: NextConfig = {
  output: "standalone", // minimal production image (see Dockerfile)
  poweredByHeader: false,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    if (process.env.NODE_ENV !== "production") return [];
    return [{ source: "/:path*", headers: [{ key: "Content-Security-Policy", value: CSP }] }];
  },
};

export default nextConfig;
