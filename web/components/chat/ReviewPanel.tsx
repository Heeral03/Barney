"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { compact } from "@/lib/format";
import type { ReviewSummary } from "@/lib/types";

/** "What buyers say": the star split and the common praise and complaints, read for you so you needn't open the store page. */
export function ReviewPanel({ token }: { token: string }) {
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [data, setData] = useState<ReviewSummary | null>(null);

  async function load() {
    setState("loading");
    try {
      setData(await api.reviewSummary(token));
      setState("idle");
    } catch {
      setState("error");
    }
  }

  if (!data) {
    return (
      <button onClick={load} disabled={state === "loading"} className="w-full rounded-lg border border-line-strong py-2 text-[13px] transition hover:bg-tint/70 disabled:opacity-60">
        {state === "loading" ? "Reading the reviews…" : state === "error" ? "Couldn’t read the reviews, retry" : "What buyers say"}
      </button>
    );
  }

  const nothing = !data.split.length && !data.praise.length && !data.complaints.length;
  return (
    <div className="rounded-lg bg-[#faf8f5] p-3 text-[12.5px] leading-5" aria-live="polite">
      {nothing ? <p className="text-muted">Nobody has written reviews for this listing yet.</p> : (
        <>
          {data.rating ? <p className="font-medium">{data.rating} from {compact(data.count ?? 0)} ratings</p> : null}
          {data.split.length > 0 && (
            <ul className="mt-2 space-y-1" aria-label="Rating split">
              {data.split.map((s) => (
                <li key={s.stars} className="flex items-center gap-2">
                  <span className="w-6 shrink-0 text-muted">{s.stars}★</span>
                  <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-tint"><span className="block h-full rounded-full bg-ink/60" style={{ width: `${s.percent}%` }} /></span>
                  <span className="w-8 shrink-0 text-right text-muted">{s.percent}%</span>
                </li>
              ))}
            </ul>
          )}
          {data.praise.length > 0 && <ul className="mt-3 space-y-1 text-sage-ink">{data.praise.map((p) => <li key={p}>✓ {p}</li>)}</ul>}
          {data.complaints.length > 0 && <ul className="mt-2 space-y-1 text-[#8a5a1c]">{data.complaints.map((c) => <li key={c}>⚠ {c}</li>)}</ul>}
          {data.verdict && <p className="mt-3 text-ink/80">{data.verdict}</p>}
        </>
      )}
    </div>
  );
}
