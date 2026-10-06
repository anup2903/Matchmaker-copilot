// The browser only ever talks to this Next.js server; /api/* is proxied to the FastAPI backend.
// That keeps the backend URL (and everything behind it, including the LLM key) off the client.
const backend = process.env.BACKEND_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
