import type { Offer } from "@/lib/types";
import { Img } from "../Img";

/** What the page shows while Barney works: a status line, then the candidates as they are ranked, then grey placeholders. */
export function Working({ status, preview }: { status: string; preview: Offer[] }) {
  return (
    <div className="space-y-5" role="status" aria-live="polite">
      <div className="flex items-center gap-3 py-1">
        <span className="flex items-center gap-1.5" aria-hidden>
          <span className="dot h-1.5 w-1.5 rounded-full bg-ink/60" /><span className="dot h-1.5 w-1.5 rounded-full bg-ink/60" /><span className="dot h-1.5 w-1.5 rounded-full bg-ink/60" />
        </span>
        <span className="text-[14px] text-muted">{status || "Thinking…"}</span>
      </div>
      {preview.length > 0 && (
        <div>
          <p className="mb-3 text-[12.5px] text-faint">Found so far, still choosing the best one…</p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {preview.map((p) => (
              <div key={p.number} className="rounded-xl border border-line bg-card p-2.5 opacity-80">
                <div className="grid h-[84px] place-items-center rounded-lg bg-[#f7f5f1]">
                  {p.image_url ? <Img src={p.image_url} className="h-full w-full object-contain p-1.5 mix-blend-multiply" /> : null}
                </div>
                <p className="mt-2 line-clamp-2 text-[12px] leading-4">{p.title}</p>
                <p className="mt-1 text-[12.5px] font-medium">{p.price_display}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function SkeletonCards({ count = 1 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" aria-hidden>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="animate-pulse rounded-2xl border border-line bg-card p-3.5">
          <div className="h-[170px] rounded-xl bg-[#f1eee9]" />
          <div className="mt-4 h-3.5 w-11/12 rounded bg-[#f1eee9]" />
          <div className="mt-2 h-3.5 w-7/12 rounded bg-[#f1eee9]" />
          <div className="mt-4 h-5 w-24 rounded bg-[#f1eee9]" />
          <div className="mt-5 h-10 rounded-lg bg-[#f1eee9]" />
        </div>
      ))}
    </div>
  );
}
