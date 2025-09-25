/** @type {import('next').NextConfig} */
const nextConfig = {
  // This will bypass ESLint errors during the build process on Vercel.
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;