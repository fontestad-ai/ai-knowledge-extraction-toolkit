import { ratelimit } from "@/lib/rate-limit";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|logos/|data/).*)"],
};

function hasBody(method: string): boolean {
  return method !== "GET" && method !== "HEAD";
}

export default async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/api")) {
    if (ratelimit && request.method === "POST") {
      try {
        const ip =
          request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
          request.headers.get("x-real-ip") ??
          "anonymous";

        const { success, limit, remaining, reset } = await ratelimit.limit(ip);

        if (!success) {
          return NextResponse.json(
            { error: "Too many requests. Please try again shortly." },
            {
              status: 429,
              headers: {
                "X-RateLimit-Limit": limit.toString(),
                "X-RateLimit-Remaining": remaining.toString(),
                "X-RateLimit-Reset": reset.toString(),
              },
            },
          );
        }
      } catch (error) {
        console.warn(
          "[rate-limit] Redis unavailable, skipping rate limit:",
          error instanceof Error ? error.message : error,
        );
      }
    }

    const backendPath = pathname.replace(/^\/api/, "");
    const targetUrl = `${BACKEND_URL}${backendPath}${request.nextUrl.search}`;

    const headers = new Headers();
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);

    try {
      let body: ArrayBuffer | null = null;
      if (hasBody(request.method)) {
        body = await request.arrayBuffer();
        headers.set("content-length", body.byteLength.toString());
      }

      const response = await fetch(targetUrl, {
        method: request.method,
        headers,
        body,
      });

      if (response.headers.get("content-type")?.includes("text/event-stream")) {
        return new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
          },
        });
      }

      return new NextResponse(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: new Headers(response.headers),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Proxy error";
      return NextResponse.json({ error: message }, { status: 502 });
    }
  }

  const response = NextResponse.next({ request });
  response.headers.set("x-current-path", pathname);
  return response;
}
