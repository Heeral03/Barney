"use client";

import { useEffect, useRef } from "react";
import { useBarney } from "@/lib/barney";
import { Thread } from "@/components/chat/Thread";
import { Hero } from "@/components/home/Hero";
import { Challenge } from "@/components/home/Challenge";
import { PopularSearches } from "@/components/home/PopularSearches";
import { Stats } from "@/components/home/Stats";
import { WishlistPeek } from "@/components/home/WishlistPeek";
import { RecentComparisons } from "@/components/home/RecentComparisons";

export default function Home() {
  const { turns, ready, send } = useBarney();
  const sent = useRef(false);

  // "/app?q=laptop for coding" comes from the landing page: start that search once.
  useEffect(() => {
    if (!ready || sent.current) return;
    sent.current = true;
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) {
      window.history.replaceState(null, "", "/app");
      void send(q);
    }
  }, [ready, send]);

  if (turns.length > 0) {
    return <div className="px-5 md:px-9"><Thread /></div>;
  }

  return (
    <div className="mx-auto max-w-[1000px] space-y-14 px-5 pb-20 md:px-9">
      <div>
        <Hero />
        <Stats />
      </div>
      <PopularSearches />
      <RecentComparisons />
      <div className="grid gap-14 md:grid-cols-[1.4fr_1fr] md:gap-12">
        <WishlistPeek />
        <Challenge />
      </div>
    </div>
  );
}
