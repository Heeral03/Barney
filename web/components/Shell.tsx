"use client";

import type { ReactNode } from "react";
import { BarneyProvider } from "@/lib/barney";
import { MobileNav, Sidebar } from "./Sidebar";
import { SearchBar } from "./SearchBar";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <BarneyProvider>
      <MobileNav />
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-20 bg-paper/90 px-5 pb-3 pt-5 backdrop-blur md:px-9 md:pt-6">
            <SearchBar />
          </header>
          {children}
        </div>
      </div>
    </BarneyProvider>
  );
}
