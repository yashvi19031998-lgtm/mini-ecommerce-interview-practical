/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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

