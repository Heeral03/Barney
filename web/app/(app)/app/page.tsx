"use client";

import { useBarney } from "@/lib/barney";
import { Thread } from "@/components/chat/Thread";
import { Hero } from "@/components/home/Hero";
import { PopularSearches } from "@/components/home/PopularSearches";
import { RecentComparisons } from "@/components/home/RecentComparisons";
import { RightRail } from "@/components/home/RightRail";

export default function Home() {
  const { turns } = useBarney();

  if (turns.length > 0) {
    return <div className="px-5 md:px-9"><Thread /></div>;
  }

  return (
    <div className="grid gap-12 px-5 md:px-9 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="min-w-0">
        <Hero />
        <PopularSearches />
        <RecentComparisons />
      </div>
      <RightRail />
    </div>
  );
}
