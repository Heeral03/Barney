"use client";

import Link from "next/link";
import { signIn, signOut } from "next-auth/react";
import { usePathname } from "next/navigation";
import { useBarney } from "@/lib/barney";
import { initials } from "@/lib/format";
import { Img } from "./Img";
import { ProfileSwitcher } from "./ProfileSwitcher";
import { CalendarIcon, GearIcon, HeartIcon, SearchIcon, UserIcon } from "./icons";

const NAV = [
  { href: "/app", label: "Compare", Icon: SearchIcon },
  { href: "/wishlist", label: "Wishlist", Icon: HeartIcon },
  { href: "/budget", label: "Budget", Icon: CalendarIcon },
  { href: "/preferences", label: "My Preferences", Icon: UserIcon },
] as const;

export function Logo({ className = "" }: { className?: string }) {
  return <span className={`font-serif tracking-tight text-ink ${className}`}>Barney</span>;
}

/** The current conversation belongs to whoever just left: the next person on this browser starts fresh. */
function forgetThisDevice() {
  try {
    localStorage.removeItem("barney_thread");
  } catch {}
}

export function Sidebar() {
  const path = usePathname();
  const { overview, newChat, turns, account, ready } = useBarney();
  const name = account?.name ?? overview?.name;

  return (
    <aside className="sticky top-0 hidden h-screen w-[268px] shrink-0 flex-col border-r border-line bg-sidebar px-[18px] py-9 md:flex">
      <Link href="/app" onClick={() => turns.length && newChat()} className="px-4">
        <Logo className="text-[40px] leading-none" />
      </Link>

      <nav className="mt-12 flex flex-col gap-1.5">
        {NAV.map(({ href, label, Icon }) => {
          const active = path.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={() => href === "/app" && turns.length && newChat()}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-4 rounded-xl px-4 py-3 text-[15px] transition-colors ${
                active ? "bg-[#f1eee9] text-ink" : "text-ink/80 hover:bg-tint/70"
              }`}
            >
              <Icon width={22} height={22} />
              {label}
              {href === "/wishlist" && (overview?.alerts ?? 0) > 0 && (
                <span className="ml-auto grid h-5 min-w-5 place-items-center rounded-full bg-danger px-1.5 text-[11px] text-white" aria-label={`${overview?.alerts} price alerts`}>{overview?.alerts}</span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-line pt-5">
        <ProfileSwitcher />
        <Link href="/preferences" className="flex items-center gap-3 rounded-xl px-1 py-1 hover:bg-tint/60">
          <span className="grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-full bg-[#e9e4da] text-[13px] font-medium text-ink/70">
            {account?.image ? <Img src={account.image} className="h-full w-full object-cover" /> : initials(name)}
          </span>
          <span className="min-w-0 flex-1 leading-tight">
            <span className="block truncate text-[14px]">{name ?? "Guest shopper"}</span>
            <span className="block truncate text-[12px] text-faint">{account ? account.email : "Not saved to an account"}</span>
          </span>
          <GearIcon width={18} height={18} className="text-faint" />
        </Link>
        {ready && (account ? (
          <button onClick={() => { forgetThisDevice(); signOut({ callbackUrl: "/" }); }} className="mt-3 w-full rounded-lg border border-line-strong py-2 text-[13px] text-ink/80 transition hover:bg-tint/70">
            Sign out
          </button>
        ) : (
          <button onClick={() => signIn("google", { callbackUrl: "/app" })} className="mt-3 w-full rounded-lg bg-ink py-2.5 text-[13.5px] text-white transition hover:bg-ink/85">
            Sign in with Google
          </button>
        ))}
      </div>
    </aside>
  );
}

/** Small screens: the logo and who you are shopping for on top, the four places as labelled tabs along the bottom (thumb reach). */
export function MobileNav() {
  const path = usePathname();
  const { overview } = useBarney();
  return (
    <>
      <div className="flex items-center justify-between gap-4 border-b border-line bg-sidebar px-5 py-3 md:hidden">
        <Link href="/app"><Logo className="text-[28px] leading-none" /></Link>
        <div className="w-40"><ProfileSwitcher compact /></div>
      </div>
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-line bg-sidebar/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {NAV.map(({ href, label, Icon }) => {
          const active = path.startsWith(href);
          return (
            <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`relative flex flex-col items-center gap-1 py-2.5 text-[11px] ${active ? "text-ink" : "text-muted"}`}>
              <Icon width={22} height={22} />
              {label === "My Preferences" ? "Preferences" : label}
              {href === "/wishlist" && (overview?.alerts ?? 0) > 0 && <span className="absolute right-[28%] top-1.5 h-2.5 w-2.5 rounded-full bg-danger" aria-label="Price alerts" />}
            </Link>
          );
        })}
      </nav>
    </>
  );
}
