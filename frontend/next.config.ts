/** @type {import('next').NextConfig} */
const nextConfig = {
  // This will bypass ESLint errors during the build.
  eslint: {
    ignoreDuringBuilds: true,
  },
  // This will bypass TypeScript errors during the build.
  typescript: {
    ignoreBuildErrors: true,
  },
};

export default nextConfig;