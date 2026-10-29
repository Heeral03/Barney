"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { useBarney } from "@/lib/barney";
import { greeting, inr } from "@/lib/format";
import { ArtFor } from "../illustrations";
import { Img } from "../Img";
import { ArrowRight, CalendarIcon, GearIcon, HeartIcon, SparkIcon, SunIcon } from "../icons";

const noSubscribe = () => () => {};
/** The time of day is only known in the browser, so the server render says a plain "Hello". */
function useGreeting(): string {
  return useSyncExternalStore(noSubscribe, () => greeting(), () => "Hello");
}

function Tile({ icon, label, value, sub, href }: { icon: React.ReactNode; label: string; value: string; sub: string; href: string }) {
  return (
    <Link href={href} className="rounded-xl border border-line bg-card p-4 transition hover:border-line-strong">
      <span className="text-ink/80">{icon}</span>
      <p className="mt-3 text-[14px]">{label}</p>
      <p className="mt-0.5 text-[15px] font-medium">{value}</p>
      <p className="text-[13px] text-faint">{sub}</p>
    </Link>
  );
}

export function RightRail() {
  const { overview, ready } = useBarney();
  const hello = useGreeting();
  const name = overview?.name;
  const stats = overview?.stats;
  const budget = overview?.budget;
  const wish = overview?.wishlist ?? [];

  return (
    <aside className="hidden xl:block">
      <div className="sticky top-[88px] space-y-8 pb-10">
        <section className="rounded-2xl border border-line bg-[#faf8f5] p-5">
          <p className="flex items-center gap-3 font-serif text-[22px]">
            <SunIcon className="text-amber" width={22} height={22} />
            {hello}{name ? `, ${name}` : ""}
          </p>
          <p className="mt-2 text-[14px] text-muted">Here’s a quick look at your shopping journey.</p>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <Tile href="/wishlist" icon={<HeartIcon />} label="Wishlist" value={`${stats?.wishlist ?? 0}`} sub={stats?.wishlist === 1 ? "item" : "items"} />
            <Tile
              href="/budget"
              icon={<CalendarIcon />}
              label="Budget"
              value={budget?.remaining != null ? inr(budget.remaining) : "Not set"}
              sub={budget?.remaining != null ? "remaining" : "Set one"}
            />
            <Tile href="/app" icon={<CompareGlyph />} label="Comparisons" value={`${stats?.comparisons ?? 0}`} sub="made" />
            <Tile href="/preferences" icon={<GearIcon />} label="Preferences" value={`${stats?.preferences ?? 0}`} sub="saved" />
          </div>
        </section>

        <section>
          <div className="flex items-baseline justify-between">
            <h2 className="font-serif text-[20px]">Your Wishlist</h2>
            <Link href="/wishlist" className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">View all <ArrowRight width={15} height={15} /></Link>
          </div>
          {ready && wish.length === 0 ? (
            <p className="mt-4 text-[14px] leading-6 text-muted">Tap the heart on any product and it will wait for you here.</p>
          ) : (
            <ul className="mt-3 divide-y divide-line">
              {wish.map((w) => {
                return (
                  <li key={w.id} className="flex items-center gap-4 py-4">
                    <div className="grid h-[68px] w-[84px] shrink-0 place-items-center rounded-lg bg-[#f7f5f1]">
                      {w.image_url ? <Img src={w.image_url} className="h-full w-full object-contain p-1.5 mix-blend-multiply" /> : <ArtFor text={w.title} className="h-12 w-14" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-1 text-[14px] font-medium">{w.title}</p>
                      <p className="mt-0.5 text-[13px] text-muted">{w.price_display}{w.seller ? ` · ${w.seller}` : ""}</p>
                      <p className="mt-1 text-[12px] text-faint">{w.target_inr ? `Target: ${inr(w.target_inr)}` : "No target price yet"}</p>
                    </div>
                    <HeartIcon className="shrink-0 text-ink/70" width={19} height={19} />
                  </li>
                );
              })}
            </ul>
          )}
          {wish.length > 0 && (
            <Link href="/wishlist" className="mt-1 inline-flex items-center gap-1.5 border-t border-line pt-4 text-[13px] text-muted underline-offset-4 hover:text-ink hover:underline">
              View all wishlist items <ArrowRight width={15} height={15} />
            </Link>
          )}
        </section>

        <section className="rounded-2xl border border-line bg-[#faf8f5] p-5">
          <div className="flex gap-4">
            <SparkIcon className="mt-1 shrink-0 text-ink/80" width={26} height={26} />
            <div>
              <p className="font-serif text-[18px]">Challenge accepted.</p>
              <p className="mt-2 text-[13px] leading-6 text-muted">Barney remembers what you like, checks prices across stores, and makes sure you never overpay. Because you’re awesome, and so are your purchases.</p>
              <Link href="/preferences" className="mt-3 inline-flex items-center gap-1.5 text-[13px] underline underline-offset-4 hover:text-muted">
                See what Barney remembers <ArrowRight width={15} height={15} />
              </Link>
            </div>
          </div>
        </section>
      </div>
    </aside>
  );
}

function CompareGlyph() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3.5" y="5" width="7" height="14" rx="1.8" /><rect x="13.5" y="5" width="7" height="14" rx="1.8" />
    </svg>
  );
}
