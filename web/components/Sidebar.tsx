"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useBarney } from "@/lib/barney";
import { initials } from "@/lib/format";
import { CalendarIcon, GearIcon, HeartIcon, SearchIcon, UserIcon } from "./icons";

const NAV = [
  { href: "/", label: "Compare", Icon: SearchIcon },
  { href: "/wishlist", label: "Wishlist", Icon: HeartIcon },
  { href: "/budget", label: "Budget", Icon: CalendarIcon },
  { href: "/preferences", label: "My Preferences", Icon: UserIcon },
] as const;

export function Logo({ className = "" }: { className?: string }) {
  return <span className={`font-serif tracking-tight text-ink ${className}`}>Barney</span>;
}

export function Sidebar() {
  const path = usePathname();
  const { overview, newChat, turns } = useBarney();
  const name = overview?.name;

  return (
    <aside className="sticky top-0 hidden h-screen w-[268px] shrink-0 flex-col border-r border-line bg-sidebar px-[18px] py-9 md:flex">
      <Link href="/" onClick={() => turns.length && newChat()} className="px-4">
        <Logo className="text-[40px] leading-none" />
      </Link>

      <nav className="mt-12 flex flex-col gap-1.5">
        {NAV.map(({ href, label, Icon }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={() => href === "/" && turns.length && newChat()}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-4 rounded-xl px-4 py-3 text-[15px] transition-colors ${
                active ? "bg-[#f1eee9] text-ink" : "text-ink/80 hover:bg-tint/70"
              }`}
            >
              <Icon width={22} height={22} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-line pt-5">
        <Link href="/preferences" className="flex items-center gap-3 rounded-xl px-1 py-1 hover:bg-tint/60">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[#e9e4da] text-[13px] font-medium text-ink/70">
            {initials(name)}
          </span>
          <span className="min-w-0 flex-1 leading-tight">
            <span className="block truncate text-[14px]">{name ?? "Guest shopper"}</span>
            <span className="block truncate text-[12px] text-faint">{name ? "Saved on this device" : "Tell Barney your name"}</span>
          </span>
          <GearIcon width={18} height={18} className="text-faint" />
        </Link>
      </div>
    </aside>
  );
}

/** Small screens: the same four places, as a quiet strip along the top. */
export function MobileNav() {
  const path = usePathname();
  return (
    <div className="flex items-center justify-between border-b border-line bg-sidebar px-5 py-3 md:hidden">
      <Link href="/"><Logo className="text-[28px] leading-none" /></Link>
      <nav className="flex gap-1">
        {NAV.map(({ href, label, Icon }) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link key={href} href={href} aria-label={label} className={`rounded-lg p-2 ${active ? "bg-[#f1eee9]" : ""}`}>
              <Icon width={21} height={21} />
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
