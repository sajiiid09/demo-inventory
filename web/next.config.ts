import os from "os";
import path from "path";
import type { NextConfig } from "next";

/**
 * Origins the dev server accepts for its own /_next/* assets and its
 * hot-reload socket. Without this, opening the app over the network
 * (http://192.168.1.x:3000) has the dev server refuse those requests.
 *
 * Next matches these as hostnames, not CIDR ranges, so the machine's own
 * addresses are enumerated at startup — the list stays correct when DHCP
 * hands out a different IP. Add more with NEXT_DEV_ORIGINS (comma-separated).
 */
function localAddresses(): string[] {
  return Object.values(os.networkInterfaces())
    .flat()
    .filter((iface): iface is os.NetworkInterfaceInfo => Boolean(iface) && !iface!.internal)
    .map((iface) => iface.address);
}

const nextConfig: NextConfig = {
  // The workspace root is this app directory, not wherever a stray lockfile lives.
  outputFileTracingRoot: path.join(__dirname),
  allowedDevOrigins: [
    "localhost",
    "127.0.0.1",
    ...localAddresses(),
    ...(process.env.NEXT_DEV_ORIGINS?.split(",").map((o) => o.trim()).filter(Boolean) ?? []),
  ],
};

export default nextConfig;
