import type { ReactNode } from "react";

/** One labelled block of the home page: a small label, a serif title, an optional action on the right. */
export function Section({ label, title, action, children, className = "" }: { label: string; title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`border-t border-line pt-10 ${className}`}>
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[11.5px] font-medium uppercase tracking-[0.16em] text-faint">{label}</p>
          <h2 className="mt-2 font-serif text-[26px] leading-tight tracking-[-0.01em]">{title}</h2>
        </div>
        {action}
      </div>
      <div className="mt-6">{children}</div>
    </section>
  );
}
