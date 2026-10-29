"use client";

import Link from "next/link";
import { signIn } from "next-auth/react";

export function StartButton() {
  return (
    <Link href="/app" className="rounded-full bg-ink px-7 py-3.5 text-[15px] text-white transition hover:bg-ink/85">
      Start shopping
    </Link>
  );
}

export function SignInButton({ className = "" }: { className?: string }) {
  return (
    <button onClick={() => signIn("google", { callbackUrl: "/app" })} className={className}>
      Sign in with Google
    </button>
  );
}
