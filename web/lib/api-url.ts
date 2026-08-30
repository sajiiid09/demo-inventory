/**
 * Where the BROWSER should reach the API.
 *
 * Distinct from lib/api.ts, which is server-side: that runs inside the Next
 * process and uses API_BASE_URL. This one is compiled into client components,
 * so the URL has to be reachable from whatever machine has the page open.
 *
 * Defaulting to "localhost" breaks the moment the app is opened over the
 * network (http://192.168.1.x:3000): the browser would look for the API on
 * the viewer's own machine. Following the page's own hostname instead means
 * localhost works from localhost, and a LAN address works over the LAN, with
 * nothing to configure.
 *
 * Set NEXT_PUBLIC_API_URL to override — a different host, or a port other
 * than 8000.
 */

export const API_PORT = 8000;

export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured) return configured;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:${API_PORT}`;
  }
  return `http://localhost:${API_PORT}`;
}
