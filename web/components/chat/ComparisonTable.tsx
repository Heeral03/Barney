"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { compact, inr } from "@/lib/format";
import type { CompareTable, TableRow } from "@/lib/types";
import { CheckIcon, StarIcon } from "../icons";
import { Img } from "../Img";

const Cell = ({ best, win, children, head }: { best?: boolean; win?: boolean; children: React.ReactNode; head?: boolean }) => {
  const Tag = head ? "th" : "td";
  return <Tag className={`min-w-[170px] px-4 py-3 text-left align-top ${win ? "bg-sage-bg/60" : best ? "bg-[#faf8f5]" : ""}`}>{children}</Tag>;
};

const Label = ({ children }: { children: React.ReactNode }) => (
  <th scope="row" className="sticky left-0 z-10 w-[120px] min-w-[120px] bg-card px-4 py-3 text-left align-top text-[12.5px] font-normal text-muted">{children}</th>
);

const Section = ({ children, span }: { children: React.ReactNode; span: number }) => (
  <tr><th colSpan={span} className="bg-sidebar px-4 py-2 text-left text-[11px] font-medium uppercase tracking-[0.12em] text-faint">{children}</th></tr>
);

const Winner = ({ children }: { children: React.ReactNode }) => (
  <span className="ml-2 rounded-full bg-sage-bg px-2 py-0.5 text-[10.5px] font-medium text-sage-ink">{children}</span>
);

/** The cost of getting it from the store it is listed at: the delivery fee and the total, when the store says. */
function totalOf(r: TableRow) {
  const store = r.stores?.find((s) => s.name === r.seller) ?? r.stores?.[0];
  if (!store) return { total: null as number | null, note: "" };
  const free = !store.shipping || /free/i.test(store.shipping);
  return { total: store.total_inr ?? (free && r.price_inr ? r.price_inr : null), note: store.shipping ? (free ? "Free delivery" : `+ ${store.shipping} delivery`) : "" };
}

/** How a column compares with Barney's pick, from numbers only: price, rating, reviews, age of the model. */
function versus(r: TableRow, pick: TableRow | undefined): { good: string[]; bad: string[] } {
  const good: string[] = [], bad: string[] = [];
  if (!pick || r.number === pick.number) return { good, bad };
  if (r.price_inr && pick.price_inr && r.price_inr !== pick.price_inr) {
    (r.price_inr < pick.price_inr ? good : bad).push(`${inr(Math.abs(r.price_inr - pick.price_inr))} ${r.price_inr < pick.price_inr ? "cheaper" : "more"}`);
  }
  if (r.rating && pick.rating && Math.abs(r.rating - pick.rating) >= 0.2) (r.rating > pick.rating ? good : bad).push(r.rating > pick.rating ? "Rated higher" : "Rated lower");
  else if (!r.rating && pick.rating) bad.push("No ratings");
  if ((r.rating_count ?? 0) > 2 * (pick.rating_count ?? 0) && (r.rating_count ?? 0) >= 100) good.push("Far more reviews");
  if (r.year && pick.year && r.year !== pick.year) (r.year > pick.year ? good : bad).push(r.year > pick.year ? "Newer model" : "Older model");
  return { good, bad };
}

/** Side by side: options as columns. The best in each row is marked, each column says where it beats or trails Barney's pick,
 *  and any column can be dropped to compare the rest. */
export function ComparisonTable({ table, title, readOnly = false }: { table: CompareTable; title?: string; readOnly?: boolean }) {
  const [hidden, setHidden] = useState<number[]>([]);
  const [shared, setShared] = useState<{ url: string; copied: boolean } | "busy" | "error" | null>(null);
  const rows = table.rows.filter((r) => !hidden.includes(r.number));
  const span = rows.length + 1;
  const pick = table.rows.find((r) => r.best);

  const prices = rows.map((r) => r.price_inr).filter((p): p is number => !!p);
  const lowest = prices.length > 1 ? Math.min(...prices) : null;
  const rated = rows.filter((r) => r.rating && (r.rating_count ?? 0) >= 20);
  const topRated = rated.length > 1 ? rated.reduce((a, b) => ((b.rating ?? 0) > (a.rating ?? 0) || ((b.rating ?? 0) === (a.rating ?? 0) && (b.rating_count ?? 0) > (a.rating_count ?? 0)) ? b : a)).number : null;
  const years = rows.map((r) => r.year).filter((y): y is number => !!y);
  const newest = years.length > 1 && new Set(years).size > 1 ? Math.max(...years) : null;
  const totals = rows.map((r) => totalOf(r).total).filter((t): t is number => !!t);
  const cheapestTotal = totals.length > 1 ? Math.min(...totals) : null;

  async function share() {
    setShared("busy");
    try {
      const { id } = await api.share(title ?? "Comparison", table);
      const url = `${window.location.origin}/s/${id}`;
      let copied = false;
      try {
        if (navigator.share) await navigator.share({ title: title ?? "Barney comparison", url });
        else { await navigator.clipboard.writeText(url); copied = true; }
      } catch {
        try { await navigator.clipboard.writeText(url); copied = true; } catch {}
      }
      setShared({ url, copied });
    } catch {
      setShared("error");
    }
  }

  return (
    <div className="rise">
      {!readOnly && (
        <div className="mb-3 flex flex-wrap items-center gap-3 text-[13px]">
          <button onClick={share} disabled={shared === "busy"} className="rounded-full border border-line-strong px-4 py-1.5 transition hover:bg-tint/70 disabled:opacity-60">
            {shared === "busy" ? "Making a link…" : "Share this comparison"}
          </button>
          {typeof shared === "object" && shared && (
            <span className="text-muted">{shared.copied ? "Link copied: " : "Link: "}<a href={shared.url} className="underline underline-offset-4">{shared.url}</a></span>
          )}
          {shared === "error" && <span className="text-danger">Couldn’t make a link. Try again.</span>}
          {hidden.length > 0 && (
            <button onClick={() => setHidden([])} className="text-muted underline underline-offset-4 hover:text-ink">Show all {table.rows.length} options</button>
          )}
        </div>
      )}
      <div className="overflow-x-auto rounded-2xl border border-line bg-card">
        <table className="w-full border-collapse text-[13.5px]">
          <caption className="sr-only">Side-by-side comparison of {rows.length} options</caption>
          <thead>
            <tr>
              <th className="w-[120px] min-w-[120px]"><span className="sr-only">Feature</span></th>
              {rows.map((r) => (
                <Cell key={r.number} head best={r.best}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="grid h-16 w-16 place-items-center rounded-lg bg-[#f7f5f1]">{r.image_url ? <Img src={r.image_url} className="h-full w-full object-contain p-1 mix-blend-multiply" /> : null}</div>
                    {!readOnly && rows.length > 2 && (
                      <button onClick={() => setHidden((h) => [...h, r.number])} aria-label={`Remove ${r.title} from the comparison`} className="rounded-full px-2 text-[16px] leading-none text-faint hover:bg-tint hover:text-ink">×</button>
                    )}
                  </div>
                  <p className="mt-2 line-clamp-3 font-medium leading-5">{r.title}</p>
                  {r.best && <span className="mt-2 inline-block rounded-full bg-sage-bg px-2.5 py-0.5 text-[11px] text-sage-ink">Barney’s pick</span>}
                </Cell>
              ))}
            </tr>
          </thead>
          <tbody className="[&_tr:not(:first-child)]:border-t [&_tr]:border-line">
            <tr>
              <Label>Price</Label>
              {rows.map((r) => (
                <Cell key={r.number} best={r.best} win={lowest !== null && r.price_inr === lowest}>
                  <span className="text-[16px] font-medium">{r.price_display}</span>
                  {r.price_verified && <span className="ml-1.5 inline-flex items-center text-[12px] text-sage-ink"><CheckIcon /></span>}
                  {lowest !== null && r.price_inr === lowest && <Winner>Lowest</Winner>}
                </Cell>
              ))}
            </tr>
            <tr>
              <Label>With delivery</Label>
              {rows.map((r) => {
                const { total, note } = totalOf(r);
                return (
                  <Cell key={r.number} best={r.best} win={cheapestTotal !== null && total === cheapestTotal}>
                    {total ? <><span className="font-medium">{inr(total)}</span><span className="block text-[12px] text-muted">{note}</span></> : <span className="text-faint">not stated</span>}
                  </Cell>
                );
              })}
            </tr>
            <tr>
              <Label>Sold by</Label>
              {rows.map((r) => (
                <Cell key={r.number} best={r.best}>
                  <p>{r.seller}{r.seller_trusted === false ? " ⚠" : ""}</p>
                  {r.link ? (
                    <a href={r.link} target="_blank" rel="noopener noreferrer" onClick={() => !readOnly && api.event("open", "", r.title)} className="mt-2 inline-block rounded-lg bg-ink px-3.5 py-1.5 text-[12.5px] text-white transition hover:bg-ink/85">Buy</a>
                  ) : (
                    <p className="mt-1 text-[12px] text-faint">no seller link yet</p>
                  )}
                </Cell>
              ))}
            </tr>
            <tr>
              <Label>Rating</Label>
              {rows.map((r) => (
                <Cell key={r.number} best={r.best} win={topRated === r.number}>
                  {r.rating ? <span className="inline-flex items-center gap-1.5"><StarIcon className="text-amber" />{r.rating}{r.rating_count ? <span className="text-faint">({compact(r.rating_count)})</span> : null}</span> : <span className="text-faint">no ratings</span>}
                  {topRated === r.number && <Winner>Best rated</Winner>}
                </Cell>
              ))}
            </tr>
            {newest !== null && (
              <tr>
                <Label>Model year</Label>
                {rows.map((r) => (
                  <Cell key={r.number} best={r.best} win={r.year === newest}>
                    {r.year ? <>{r.year}{r.year === newest && <Winner>Newest</Winner>}</> : <span className="text-faint">not stated</span>}
                  </Cell>
                ))}
              </tr>
            )}
            {pick && rows.length > 1 && (
              <tr>
                <Label>Versus the pick</Label>
                {rows.map((r) => {
                  const v = versus(r, pick);
                  return (
                    <Cell key={r.number} best={r.best}>
                      {r.number === pick.number ? <span className="text-faint">—</span> : (
                        <ul className="space-y-1 text-[12.5px]">
                          {v.good.map((t) => <li key={t} className="text-sage-ink">↑ {t}</li>)}
                          {v.bad.map((t) => <li key={t} className="text-[#8a5a1c]">↓ {t}</li>)}
                          {!v.good.length && !v.bad.length && <li className="text-faint">About the same</li>}
                        </ul>
                      )}
                    </Cell>
                  );
                })}
              </tr>
            )}

            {table.specs.length > 0 && <Section span={span}>Specifications</Section>}
            {table.specs.map((spec) => (
              <tr key={spec}>
                <Label>{spec}</Label>
                {rows.map((r) => (
                  <Cell key={r.number} best={r.best}>{r.values[spec] || <span className="text-faint">not stated</span>}</Cell>
                ))}
              </tr>
            ))}

            {table.requirements.length > 0 && <Section span={span}>Your needs</Section>}
            {table.requirements.map((need) => (
              <tr key={need}>
                <Label>{need}</Label>
                {rows.map((r) => {
                  const m = r.matches[need] ?? "unknown";
                  return (
                    <Cell key={r.number} best={r.best}>
                      {m === "yes" ? <span className="font-medium text-sage-ink">✓ Yes</span> : m === "no" ? <span className="font-medium text-danger">✗ No</span> : <span className="text-faint">? Not stated</span>}
                    </Cell>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
