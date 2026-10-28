import type { ReactNode } from "react";

export function Page({ title, intro, children }: { title: string; intro?: string; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[860px] px-5 pb-20 pt-8 md:px-9 md:pt-12">
      <h1 className="font-serif text-[40px] leading-[1.05] tracking-[-0.015em] md:text-[52px]">{title}</h1>
      {intro && <p className="mt-4 max-w-xl text-[15.5px] leading-7 text-muted">{intro}</p>}
      <div className="mt-10">{children}</div>
    </div>
  );
}

export function Empty({ title, text, children }: { title: string; text: string; children?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-line-strong bg-card/60 p-10 text-center">
      <p className="font-serif text-[22px]">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-[14.5px] leading-6 text-muted">{text}</p>
      {children}
    </div>
  );
}
