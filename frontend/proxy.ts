import { NextResponse, type NextRequest } from "next/server";

/**
 * Early redirect to /login when the non-secret `cb_session` marker cookie is absent.
 * This is a UX shortcut, not security: the backend authorizes every API call and the app
 * shell re-checks /me. Guest-only pages (login/register) redirect client-side after /me
 * succeeds, so a stale marker can never cause a redirect loop.
 */
const SESSION_MARKER = "cb_session";

export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_MARKER)) return NextResponse.next();
  const { pathname, search } = request.nextUrl;
  const url = new URL("/login", request.url);
  url.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/chat/:path*",
    "/knowledge-base/:path*",
    "/sources/:path*",
    "/unanswered/:path*",
    "/settings/:path*",
  ],
};
