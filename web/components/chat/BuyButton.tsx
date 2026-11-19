"use client";

import { api } from "@/lib/api";

type Props = {
  link: string;
  title: string;
  product?: string;
  seller: string;
  /** The price on the store's own page matched what Barney shows. */
  verified?: boolean;
  price?: number | null;
  /** The shared page is read-only: nothing is recorded. */
  readOnly?: boolean;
  compact?: boolean;
};

const domainOf = (link: string) => {
  try { return new URL(link).hostname.replace(/^www\./, ""); } catch { return ""; }
};

/**
 * Barney only suggests. This sends you to the store's own page, where you finish the purchase.
 * "Buy this" when the price was confirmed on that page, "Check this out" when it was only listed.
 */
export function BuyButton({ link, title, product = "", seller, verified, price, readOnly, compact }: Props) {
  const kind = verified ? "buy" : "check";
  const label = verified ? "Buy this" : "Check this out";
  return (
    <div>
      <a
        href={link}
        target="_blank"
        rel="noopener noreferrer sponsored"
        onClick={() => !readOnly && api.event(kind, product, title, link, price)}
        className={`block rounded-lg bg-ink text-center font-medium text-white transition hover:bg-ink/85 ${compact ? "mt-2 inline-block px-3.5 py-1.5 text-[12.5px]" : "py-2.5 text-[13.5px]"}`}
      >
        {label} <span aria-hidden>↗</span>
      </a>
      {!compact && (
        <p className="mt-1.5 text-center text-[11.5px] text-faint">Opens {domainOf(link) || seller}. You finish on their site.</p>
      )}
    </div>
  );
}
