import Link from "next/link";
import { Logo } from "../Sidebar";

export function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-paper/80 backdrop-blur-md supports-[backdrop-filter]:bg-paper/70">
      <div className="mx-auto flex h-[68px] w-full max-w-[1120px] items-center justify-between px-6 md:px-10">
        <Link href="/" aria-label="Barney home">
          <Logo className="text-[28px] leading-none" />
        </Link>
        <nav aria-label="Primary" className="hidden items-center gap-8 text-[14px] text-muted md:flex">
          <a href="#how" className="transition-colors hover:text-ink">How it works</a>
          <a href="#features" className="transition-colors hover:text-ink">Features</a>
          <a href="#code" className="transition-colors hover:text-ink">The Barney code</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/signin" className="rounded-full px-4 py-2 text-[14px] text-muted transition-colors hover:text-ink">Sign in</Link>
          <Link href="/app" className="rounded-full bg-ink px-5 py-2.5 text-[14px] text-white transition-colors hover:bg-ink/85">Start shopping</Link>
        </div>
      </div>
    </header>
  );
}
