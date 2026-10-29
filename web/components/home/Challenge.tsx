import Link from "next/link";
import { ArrowRight, SparkIcon } from "../icons";
import { Section } from "./Section";

export function Challenge() {
  return (
    <Section label="The Barney code" title="Challenge accepted.">
      <div className="flex gap-4">
        <SparkIcon className="mt-0.5 shrink-0 text-ink/80" width={24} height={24} />
        <div>
          <p className="text-[14px] leading-6 text-muted">
            Barney remembers what you like, checks prices across stores, and makes sure you never overpay. Because you’re awesome, and so are your purchases.
          </p>
          <Link href="/preferences" className="mt-3 inline-flex items-center gap-1.5 text-[13px] underline underline-offset-4 hover:text-muted">
            See what Barney remembers <ArrowRight width={15} height={15} />
          </Link>
        </div>
      </div>
    </Section>
  );
}
