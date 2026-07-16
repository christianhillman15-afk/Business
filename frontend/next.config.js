/** @type {import('next').NextConfig} */

// In the static demo build (GitHub Pages) we export a fully static site and
// serve it from a sub-path like /<repo>. Both are gated on env vars so the
// normal `next dev` / `next build` (with a real backend) is unchanged.
const isStaticDemo = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const basePath = (process.env.NEXT_PUBLIC_BASE_PATH || "").replace(/\/$/, "");

const nextConfig = {
  reactStrictMode: true,
  ...(isStaticDemo
    ? {
        output: "export",
        images: { unoptimized: true },
        trailingSlash: true,
      }
    : {}),
  ...(basePath ? { basePath, assetPrefix: basePath } : {}),
};

module.exports = nextConfig;
