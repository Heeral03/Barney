"use client";

import { useEffect, useRef } from "react";
import { useBarney } from "@/lib/barney";
import { ArrowRight } from "../icons";
import { ComparisonTable } from "./ComparisonTable";
import { Markdown } from "./Markdown";
import { ProductCard } from "./ProductCard";

export function Thread() {
  const { turns, sending, send, newChat } = useBarney();
  const end = useRef<HTMLDivElement>(null);
  const lastAssistant = turns.map((t) => t.role).lastIndexOf("assistant");

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, sending]);

  return (
    <section className="mx-auto w-full max-w-[1040px] pb-40 pt-6">
      <button onClick={newChat} className="group mb-8 inline-flex items-center gap-2 text-[13px] text-muted transition hover:text-ink">
        <ArrowRight width={15} height={15} className="rotate-180 transition group-hover:-translate-x-0.5" /> New search
      </button>

      <div className="space-y-9">
        {turns.map((t, i) =>
          t.role === "user" ? (
            <div key={i} className="rise flex justify-end">
              <p className="max-w-[80%] rounded-2xl bg-tint px-5 py-3 text-[15px] leading-6">{t.content}</p>
            </div>
          ) : (
            <div key={i} className="rise space-y-5">
              <div className="max-w-[680px] text-[15.5px] text-ink/90">
                <Markdown>{t.content}</Markdown>
              </div>

              {t.products && t.products.length > 0 && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {t.products.map((p) => <ProductCard key={`${i}-${p.number}-${p.title}`} offer={p} />)}
                </div>
              )}

              {t.table && <ComparisonTable table={t.table} />}

              {i === lastAssistant && !sending && t.options && t.options.length > 0 && (
                <div className="flex flex-wrap gap-2.5">
                  {t.options.map((o) => (
                    <button key={o} onClick={() => send(o)} className="rounded-full border border-line-strong bg-card px-4 py-2 text-[13.5px] text-ink/85 transition hover:border-ink/40 hover:bg-tint/60">
                      {o}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ),
        )}

        {sending && (
          <div className="flex items-center gap-1.5 py-2" aria-label="Barney is thinking">
            <span className="dot h-1.5 w-1.5 rounded-full bg-ink/60" /><span className="dot h-1.5 w-1.5 rounded-full bg-ink/60" /><span className="dot h-1.5 w-1.5 rounded-full bg-ink/60" />
          </div>
        )}
        <div ref={end} />
      </div>
    </section>
  );
}
