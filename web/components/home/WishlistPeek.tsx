"use client";

import Link from "next/link";
import { useBarney } from "@/lib/barney";
import { inr } from "@/lib/format";
import { ArrowRight } from "../icons";
import { ArtFor } from "../illustrations";
import { Img } from "../Img";
import { Section } from "./Section";

export function WishlistPeek() {
  const { overview, ready } = useBarney();
  const items = (overview?.wishlist ?? []).slice(0, 3);
  return (
    <Section
      label="Your wishlist"
      title="Saved for later"
      action={items.length ? <Link href="/wishlist" className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">View all <ArrowRight width={15} height={15} /></Link> : null}
    >
      {ready && items.length === 0 ? (
        <p className="text-[14px] leading-6 text-muted">Tap the heart on any product and it will wait for you here.</p>
      ) : (
        <ul className="divide-y divide-line">
          {items.map((w) => (
            <li key={w.id} className="flex items-center gap-4 py-3.5 first:pt-0">
              <div className="grid h-14 w-16 shrink-0 place-items-center rounded-lg bg-[#f7f5f1]">
                {w.image_url ? <Img src={w.image_url} className="h-full w-full object-contain p-1.5 mix-blend-multiply" /> : <ArtFor text={w.title} className="h-10 w-12" />}
              </div>
              <div className="min-w-0 flex-1">
                <p className="line-clamp-1 text-[14px] font-medium">{w.title}</p>
                <p className="mt-0.5 text-[13px] text-muted">{w.price_display}{w.target_inr ? ` · target ${inr(w.target_inr)}` : ""}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
