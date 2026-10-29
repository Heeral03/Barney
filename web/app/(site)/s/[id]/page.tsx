import Link from "next/link";
import { Suspense } from "react";
import { SharedView } from "@/components/SharedView";
import { Logo } from "@/components/Sidebar";

export default function SharedPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <div className="mx-auto w-full max-w-[1100px] px-6 pb-20 md:px-10">
      <header className="flex items-center justify-between py-8">
        <Link href="/"><Logo className="text-[34px] leading-none" /></Link>
        <Link href="/app" className="text-[14px] text-muted transition hover:text-ink">Make your own comparison</Link>
      </header>
      <Suspense fallback={<p className="text-muted">Opening the comparison…</p>}>
        <Loaded params={params} />
      </Suspense>
    </div>
  );
}

async function Loaded({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SharedView id={id} />;
}
