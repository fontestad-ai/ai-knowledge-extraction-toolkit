import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["*.local", "10.*"],
  reactCompiler: true,
  output: "standalone",
  images: {
    unoptimized: true,
  },
  serverExternalPackages: ["shiki"],
  experimental: {
    proxyClientMaxBodySize: "50mb",
  },
};

export default nextConfig;
