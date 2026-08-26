/**
 * Route gating from the JWT — a UX convenience only. FastAPI re-verifies the
 * token and the role on every request; it is the sole authority (ADR-007).
 */

import { NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

// Dev default mirrors the API's own documented default (.env.example). The
// middleware is a UX gate only — FastAPI verifies sessions against its own
// secret and remains the sole authority (ADR-007).
const secret = new TextEncoder().encode(
  process.env.JWT_SECRET ?? "dev-secret-change-me",
);

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const token = req.cookies.get("access_token")?.value;

  let authed = false;
  if (token) {
    try {
      await jwtVerify(token, secret);
      authed = true;
    } catch {
      authed = false;
    }
  }

  if (pathname === "/login") {
    return authed ? NextResponse.redirect(new URL("/dashboard", req.url)) : NextResponse.next();
  }
  if (!authed) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
