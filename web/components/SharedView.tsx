"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SharedComparison } from "@/lib/types";
import { ComparisonTable } from "./chat/ComparisonTable";

/** A comparison someone sent you: read-only, no account needed. */
export function SharedView({ id }: { id: string }) {
  const [data, setData] = useState<SharedComparison | "missing" | null>(null);

  useEffect(() => {
    let live = true;
    api.shared(id).then((d) => live && setData(d)).catch(() => live && setData("missing"));
    return () => { live = false; };
  }, [id]);

  if (data === null) return <p className="text-muted">Opening the comparison…</p>;
  if (data === "missing") return <p className="font-serif text-[24px]">This link doesn’t lead anywhere.</p>;
  return (
    <>
      <h1 className="font-serif text-[36px] leading-tight tracking-[-0.015em] md:text-[48px]">{data.title}</h1>
      <p className="mt-3 max-w-xl text-[15px] leading-7 text-muted">Prices were checked when this was shared and may have changed since.</p>
      <div className="mt-8"><ComparisonTable table={data.table} title={data.title} readOnly /></div>
    </>
  );
}
