import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The workspace root is this app directory, not wherever a stray lockfile lives.
  outputFileTracingRoot: path.join(__dirname),
};

export default nextConfig;
