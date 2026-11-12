/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // QA / CI builds set NEXT_DIST_DIR=.next-qa so they never overwrite the cache of a running `next dev`
  // (a build into the same .next folder broke the dev server's font cache).
  distDir: process.env.NEXT_DIST_DIR || '.next',
  experimental: {
    // Job Portal / CRM Sources searches can take up to ~60s; the default 30s
    // proxy timeout cut them off ("socket hang up" -> HTTP 500 in the browser).
    proxyTimeout: 120000,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:5000/api/:path*',
      },
    ];
  },
};

export default nextConfig;

