"use client";

import { SessionProvider } from "next-auth/react";
import type { ReactNode } from "react";
import { BarneyProvider } from "@/lib/barney";
import { MobileNav, Sidebar } from "./Sidebar";
import { Onboarding } from "./Onboarding";
import { SearchBar } from "./SearchBar";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
    <BarneyProvider>
      <a href="#main" className="sr-only z-50 rounded-lg bg-ink px-4 py-2 text-white focus:not-sr-only focus:fixed focus:left-3 focus:top-3">Skip to content</a>
      <MobileNav />
      <div className="flex min-h-screen pb-24 md:pb-0">
        <Sidebar />
        <div id="main" className="min-w-0 flex-1">
          <header className="sticky top-0 z-20 bg-paper/90 px-5 pb-3 pt-5 backdrop-blur md:px-9 md:pt-6">
            <SearchBar />
          </header>
          {children}
          <Onboarding />
        </div>
      </div>
    </BarneyProvider>
    </SessionProvider>
  );
}
