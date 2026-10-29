"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";
import { ago, compact, inr } from "@/lib/format";
import type { Offer, Store } from "@/lib/types";
import { CheckIcon, HeartIcon, StarIcon } from "../icons";
import { ArtFor } from "../illustrations";
import { Img } from "../Img";
import { ReviewPanel } from "./ReviewPanel";

/** One product. The price and the Buy link are always the seller's own; nothing sends you to a search engine. */
export function ProductCard({ offer }: { offer: Offer }) {
  const { isWished, toggleWish } = useBarney();
  const [o, setO] = useState(offer);
  const [state, setState] = useState<"idle" | "loading" | "none" | "error">("idle");
  const wished = isWished(o);
  const [feedback, setFeedback] = useState<"up" | "down" | "wrong" | null>(null);

  async function rate(verdict: "up" | "down" | "wrong") {
    setFeedback(verdict);
    api.feedback(o.title, o.product ?? "", verdict).catch(() => {});
  }

  async function compare() {
    if (!o.token) return;
    setState("loading");
    try {
      const r = await api.compare(o.token);
      if (!r.stores.length) return setState("none");
      setO({ ...o, ...(r.cheapest ?? {}), stores: r.stores });
      setState("idle");
    } catch {
      setState("error");
    }
  }

  const reliable = (o.stores ?? []).filter((s) => s.trusted);
  const lowest = Math.min(...(reliable.length ? reliable : o.stores ?? []).map((s) => s.price_inr));

  if (feedback === "wrong" || feedback === "down") {
    return (
      <article className="rise flex flex-col justify-center rounded-2xl border border-dashed border-line-strong bg-card/60 p-5 text-center text-[13px] text-muted">
        <p>Thanks, noted. I’ll use this to pick better next time.</p>
        <button onClick={() => setFeedback(null)} className="mt-2 underline underline-offset-4 hover:text-ink">Undo</button>
      </article>
    );
  }

  return (
    <article className="rise flex flex-col rounded-2xl border bg-card p-3.5 transition hover:shadow-[0_8px_24px_rgba(0,0,0,0.05)] data-[best=true]:border-ink/70" data-best={o.best ? "true" : "false"}>
      <div className="relative grid h-[170px] place-items-center rounded-xl bg-[#f7f5f1]">
        {o.image_url ? <Img src={o.image_url} className="h-full w-full object-contain p-3 mix-blend-multiply" /> : <ArtFor text={o.title} className="h-24 w-32" />}
        {o.best && <span className="absolute left-2.5 top-2.5 rounded-full bg-sage-bg px-2.5 py-1 text-[11px] font-medium text-sage-ink">Barney’s pick</span>}
        {o.over_budget && <span className="absolute bottom-2.5 left-2.5 rounded-full bg-[#f6e7d6] px-2.5 py-1 text-[11px] text-[#8a5a1c]">Over budget</span>}
        <button
          onClick={() => toggleWish(o)}
          aria-label={wished ? "Remove from wishlist" : "Save to wishlist"}
          aria-pressed={wished}
          className={`absolute right-2.5 top-2.5 grid h-8 w-8 place-items-center rounded-full bg-card/90 shadow-sm transition hover:scale-105 ${wished ? "text-danger" : "text-ink/60"}`}
        >
          <HeartIcon filled={wished} width={17} height={17} />
        </button>
      </div>

      <h3 className="mt-3.5 line-clamp-2 min-h-[40px] text-[14px] font-medium leading-5">{o.title}</h3>

      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-[19px] font-medium tracking-tight">{o.price_display}</span>
        {o.price_verified && (
          <span title="Checked on the store's own page" className="inline-flex items-center gap-0.5 text-[12px] text-sage-ink"><CheckIcon /> verified</span>
        )}
      </div>
      <p className="mt-0.5 flex items-center gap-1.5 text-[12.5px] text-muted">
        {o.seller}{o.seller_trusted === false ? " ⚠" : ""}
        {o.rating ? (<><span className="text-line-strong">·</span><StarIcon className="text-amber" />{o.rating}{o.rating_count ? <span className="text-faint">({compact(o.rating_count)})</span> : null}</>) : null}
      </p>

      {o.notes && o.notes.length > 0 && (
        <ul className="mt-3 space-y-1" aria-label="Why this one">
          {o.notes.map((n) => (
            <li key={n.text} className={`flex gap-1.5 text-[12px] leading-4 ${n.kind === "warn" ? "text-[#8a5a1c]" : "text-sage-ink"}`}>
              <span aria-hidden>{n.kind === "warn" ? "⚠" : "✓"}</span>
              <span>{n.text}</span>
            </li>
          ))}
        </ul>
      )}

      {o.stores && o.stores.length > 1 && (
        <ul className="mt-3 space-y-1 border-t border-line pt-3">
          {o.stores.slice(0, 4).map((s: Store) => {
            const cls = !s.trusted ? "text-faint" : s.price_inr === lowest ? "font-semibold text-sage-ink" : "text-ink/80";
            return (
              <li key={s.name + s.link}>
                <a href={s.link} target="_blank" rel="noopener noreferrer" title={s.trusted ? "" : "A store I can’t vouch for"} className={`flex justify-between gap-3 text-[12.5px] hover:underline ${cls}`}>
                  <span className="truncate">{s.name}{s.trusted ? "" : " ⚠"}</span>
                  <span className="shrink-0">{s.price_display}{s.verified === true || s.verified === "corrected" ? " ✓" : ""}</span>
                </a>
                {(s.shipping || s.delivery) && (
                  <p className="text-[11px] text-faint">{s.shipping && !/free/i.test(s.shipping) ? `+ ${s.shipping} delivery${s.total_inr ? `, ${inr(s.total_inr)} in all` : ""}` : "Free delivery"}{s.delivery ? ` · ${s.delivery}` : ""}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-3 text-[11.5px] text-faint">
        {o.checked_at ? `Prices checked ${ago(o.checked_at)}` : "Price from the listing; I haven’t confirmed it on the store’s page yet"}
      </p>

      <div className="mt-auto space-y-2 pt-3">
        {!o.stores?.length && o.token && (
          <button onClick={compare} disabled={state === "loading"} className="w-full rounded-lg border border-line-strong py-2 text-[13px] transition hover:bg-tint/70 disabled:opacity-60">
            {state === "loading" ? "Checking stores…" : state === "none" ? "Only this store has it" : state === "error" ? "Couldn’t compare, retry" : "Compare prices across stores"}
          </button>
        )}
        {o.token && <ReviewPanel token={o.token} />}
        {o.link ? (
          <a href={o.link} target="_blank" rel="noopener noreferrer" onClick={() => api.event("open", o.product ?? "", o.title)} className="block rounded-lg bg-ink py-2.5 text-center text-[13.5px] font-medium text-white transition hover:bg-ink/85">
            Buy at {o.seller}
          </a>
        ) : (
          <p className="rounded-lg bg-tint py-2.5 text-center text-[13px] text-muted">No direct store link for this one</p>
        )}
      </div>

      <div className="mt-3 flex items-center gap-1 border-t border-line pt-2.5 text-[12px] text-faint" role="group" aria-label="Was this a good suggestion?">
        <span className="mr-auto">Good pick?</span>
        <button onClick={() => rate("up")} aria-pressed={feedback === "up"} aria-label="Good suggestion" className={`rounded-full px-2 py-1 transition hover:bg-tint ${feedback === "up" ? "bg-sage-bg text-sage-ink" : ""}`}>👍</button>
        <button onClick={() => rate("down")} aria-label="Not a good suggestion" className="rounded-full px-2 py-1 transition hover:bg-tint">👎</button>
        <button onClick={() => rate("wrong")} className="rounded-full px-2 py-1 transition hover:bg-tint hover:text-ink">Wrong product</button>
      </div>
    </article>
  );
}
