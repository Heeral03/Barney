"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useBarney } from "@/lib/barney";
import type { FeedItem } from "@/lib/types";
import { ago } from "@/lib/format";
import { Section } from "./Section";

/** What Barney noticed without being asked: a saved product got cheaper, or one you looked at did. */
export function NoticedFeed() {
  const { ready, account, profile } = useBarney();
  const [items, setItems] = useState<FeedItem[]>([]);

  useEffect(() => {
    if (!ready) return;
    let live = true;
    api.feed().then((f) => live && setItems(f)).catch(() => {});
    return () => { live = false; };
  }, [ready, account, profile]);

  if (items.length === 0) return null;

  async function clear() {
    setItems([]);
    await api.feedSeen().catch(() => {});
  }

  return (
    <Section label="While you were away" title="Barney noticed" action={<button onClick={clear} className="text-[13px] text-muted underline underline-offset-4 hover:text-ink">Dismiss all</button>}>
      <ul className="divide-y divide-line rounded-2xl border border-line bg-card">
        {items.map((i) => (
          <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
            <div>
              <p className="text-[14.5px] font-medium">{i.title}</p>
              <p className="text-[13px] text-muted">{i.body} <span className="text-faint">· {ago(i.at)}</span></p>
            </div>
            {i.link && (
              <a href={i.link} target="_blank" rel="noopener noreferrer sponsored" className="rounded-full bg-ink px-4 py-1.5 text-[13px] text-white transition hover:bg-ink/85">Check this out ↗</a>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
}
