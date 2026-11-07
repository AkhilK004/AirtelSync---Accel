import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const LOCALES = ["en", "hi", "mr"];

// Redirect locale-less paths (/, /advisor) to /{locale}/... using Accept-Language (default en).
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (LOCALES.some((l) => pathname === `/${l}` || pathname.startsWith(`/${l}/`))) return;
  const accept = request.headers.get("accept-language")?.toLowerCase() ?? "";
  const locale = LOCALES.find((l) => l !== "en" && accept.startsWith(l)) ?? "en";
  const url = request.nextUrl.clone();
  url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  // skip Next internals, static files and the English-only back-office
  matcher: ["/((?!_next|backoffice|favicon.ico|.*\..*).*)"],
};
