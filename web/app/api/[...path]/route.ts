import { cookies } from "next/headers";
import { auth } from "@/auth";
import { backendToken } from "@/lib/backend-token";

// The browser only talks to this app. Every `/api/*` call is forwarded to the Barney back end (FastAPI) with a signed
// token saying who is calling. The browser cannot choose that: it comes from the sign-in session, or, before sign-in,
// from a random id kept in an httpOnly cookie.
const BACKEND = process.env.BARNEY_API ?? "http://127.0.0.1:8000";
const GUEST_COOKIE = "barney_guest";
const GUEST_ID = /^[0-9a-f-]{36}$/;

async function handle(req: Request, ctx: RouteContext<"/api/[...path]">): Promise<Response> {
  const { path } = await ctx.params;
  const jar = await cookies();
  const session = await auth();

  const saved = jar.get(GUEST_COOKIE)?.value;
  const guestId = saved && GUEST_ID.test(saved) ? saved : null;
  const accountId = session?.user?.id;
  const route = path.join("/");
  let body: BodyInit | undefined;

  if (route === "me/claim-guest") {
    // After sign-in: hand the back end proof of both the account and the guest it should absorb.
    if (!accountId) return Response.json({ detail: "sign in required" }, { status: 403 });
    if (!guestId) return Response.json({ claimed: false });
    body = JSON.stringify({ guest_token: await backendToken(`guest:${guestId}`) });
  }

  const newGuest = !accountId && !guestId ? crypto.randomUUID() : null;
  const sub = accountId ? `google:${accountId}` : `guest:${guestId ?? newGuest}`;
  if (newGuest) {
    jar.set(GUEST_COOKIE, newGuest, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 60 * 60 * 24 * 365 });
  }

  const headers = new Headers({ Authorization: `Bearer ${await backendToken(sub, accountId ? session?.user?.email : null)}` });
  const type = req.headers.get("content-type");
  if (type) headers.set("content-type", type);
  const profileHeader = req.headers.get("x-barney-profile");
  if (profileHeader) headers.set("x-barney-profile", profileHeader.slice(0, 60));
  if (body === undefined && req.method !== "GET" && req.method !== "HEAD") body = await req.arrayBuffer();

  let res: Response;
  try {
    res = await fetch(`${BACKEND}/${route}${new URL(req.url).search}`, { method: req.method, headers, body, cache: "no-store" });
  } catch {
    return Response.json({ detail: "Barney's back end is not reachable" }, { status: 502 });
  }
  if (route === "me/claim-guest" && res.ok) jar.delete(GUEST_COOKIE); // the guest's data now belongs to the account
  return new Response(res.body, { status: res.status, headers: { "content-type": res.headers.get("content-type") ?? "application/json" } });
}

export { handle as GET, handle as POST, handle as PUT, handle as DELETE };
