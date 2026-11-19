import { Headphones } from "../illustrations";
import { CheckIcon, StarIcon } from "../icons";

/** An illustrative recommendation, drawn in CSS so there is nothing to license. Not live data. */
export function ProductPeek() {
  return (
    <div className="elev-lg overflow-hidden rounded-[28px] border border-line bg-card">
      <div className="flex items-center gap-2 border-b border-line bg-sidebar px-5 py-3.5">
        <span aria-hidden className="h-2.5 w-2.5 rounded-full bg-line-strong" />
        <span aria-hidden className="h-2.5 w-2.5 rounded-full bg-line-strong" />
        <span aria-hidden className="h-2.5 w-2.5 rounded-full bg-line-strong" />
        <span className="ml-3 text-[12.5px] text-faint">Barney · Headphones under ₹5,000</span>
      </div>
      <div className="grid gap-8 p-6 sm:p-10 md:grid-cols-[1fr_1.15fr]">
        <div className="grid place-items-center rounded-2xl bg-tint/70 p-8">
          <Headphones className="w-full max-w-[220px]" />
        </div>
        <div className="flex flex-col">
          <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-sage-bg px-3 py-1 text-[12px] font-medium text-sage-ink">
            <CheckIcon /> Barney’s pick
          </span>
          <h3 className="mt-4 font-serif text-[30px] leading-[1.1] tracking-[-0.01em]">Wireless over-ear headphones</h3>
          <p className="mt-2 flex items-center gap-1.5 text-[13.5px] text-muted">
            <span className="flex text-amber" aria-hidden><StarIcon /><StarIcon /><StarIcon /><StarIcon /><StarIcon /></span>
            4.4 · 2,300+ reviews
          </p>
          <p className="mt-5 text-[14.5px] leading-7 text-muted">
            Fits your ₹5,000 budget, has the long battery life you asked for, and is rated higher than anything cheaper.
          </p>
          <dl className="mt-6 divide-y divide-line rounded-xl border border-line text-[13.5px]">
            {[
              ["Store A", "₹4,299", "Cheapest"],
              ["Store B", "₹4,499", "Verified"],
              ["Store C", "₹4,790", "As listed"],
            ].map(([store, price, tag], i) => (
              <div key={store} className="flex items-center justify-between px-4 py-3">
                <dt className="flex items-center gap-2">{store}{i === 0 && <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-sage-ink" />}</dt>
                <dd className="flex items-center gap-3"><span className="text-faint">{tag}</span><span className="font-medium tabular-nums">{price}</span></dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-[12px] text-faint">Illustrative example of a recommendation.</p>
        </div>
      </div>
    </div>
  );
}
