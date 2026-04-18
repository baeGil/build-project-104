/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  distDir: "dist",
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: ["localhost"],
  // Suppress verbose logging in development
  logging: {
    fetches: {
      fullUrl: false,
    },
  },
  // Turbopack configuration (Next.js 16+)
  turbopack: {
    // Suppress warnings
  },
};

export default nextConfig;