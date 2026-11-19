import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { GoogleSignIn } from "@/components/site/GoogleSignIn";
import { Logo } from "@/components/Sidebar";
import { CheckIcon } from "@/components/icons";

export const metadata: Metadata = { title: "Sign in · Barney" };

const PERKS = ["Wishlist and price drops that follow you", "Preferences Barney remembers, and you can edit", "A monthly budget that keeps you honest"];

/** Only same-site paths, so a crafted link can't bounce someone to another site after sign-in. */
function safeCallback(raw: string | string[] | undefined): string {
  const v = Array.isArray(raw) ? raw[0] : raw;
  return v && v.startsWith("/") && !v.startsWith("//") ? v : "/app";
}

type SP = Promise<{ callbackUrl?: string | string[]; error?: string }>;

/** The only part that reads the URL, so the rest of the page can be prerendered. */
async function Actions({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const callbackUrl = safeCallback(sp.callbackUrl);
  return (
    <>
      {sp.error && (
        <p role="alert" className="mt-6 rounded-xl border border-danger/30 bg-danger/5 px-4 py-3 text-[13.5px] text-danger">
          Sign-in didn’t go through. Try again, or continue as a guest.
        </p>
      )}
      <div className="mt-8 space-y-3">
        <GoogleSignIn callbackUrl={callbackUrl} />
        <div className="flex items-center gap-3 py-1 text-[12px] text-faint" aria-hidden>
          <span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" />
        </div>
        <Link href="/app" className="block w-full rounded-full bg-ink px-6 py-3.5 text-center text-[15px] font-medium text-white transition-colors hover:bg-ink/85">
          Continue as guest
        </Link>
      </div>
    </>
  );
}

export default function SignIn({ searchParams }: { searchParams: SP }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <main className="flex flex-col px-6 py-8 md:px-14">
        <Link href="/" aria-label="Barney home" className="w-fit"><Logo className="text-[30px] leading-none" /></Link>

        <div className="mx-auto flex w-full max-w-[400px] flex-1 flex-col justify-center py-16">
          <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-muted">Welcome back</p>
          <h1 className="mt-4 font-serif text-[44px] font-normal leading-[1.05] tracking-[-0.02em]">Suit up.</h1>
          <p className="mt-4 text-[15.5px] leading-7 text-muted">Sign in to pick up where you left off, with your wishlist, budget and preferences.</p>

          <Suspense fallback={<div aria-hidden className="mt-8 h-[158px]" />}>
            <Actions searchParams={searchParams} />
          </Suspense>

          <p className="mt-6 text-[12.5px] leading-6 text-faint">
            Guests can shop right away. If you sign in later, your activity moves to your account.
          </p>
        </div>
      </main>

      <aside className="relative hidden overflow-hidden bg-ink text-paper lg:flex lg:flex-col lg:justify-between lg:p-14">
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-[420px] w-[420px] rounded-full bg-amber/15 blur-3xl" />
        <p className="relative text-[12px] font-medium uppercase tracking-[0.16em] text-white/50">The Barney code</p>
        <div className="relative">
          <blockquote className="max-w-[16ch] font-serif text-[52px] leading-[1.06] tracking-[-0.02em]">
            It’s gonna be legen<span className="text-white/45 italic">… wait for it …</span>dary.
          </blockquote>
          <ul className="mt-12 space-y-4 text-[15px] text-white/70">
            {PERKS.map((p) => (
              <li key={p} className="flex items-start gap-3">
                <span aria-hidden className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-white/10 text-amber"><CheckIcon /></span>
                {p}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-[13px] text-white/40">Built for smart shoppers in India</p>
      </aside>
    </div>
  );
}
