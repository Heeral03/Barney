import Link from "next/link";
import { LandingSearch } from "@/components/LandingSearch";
import { Logo } from "@/components/Sidebar";
import { Nav } from "@/components/site/Nav";
import { ProductPeek } from "@/components/site/ProductPeek";
import { Reveal } from "@/components/site/Reveal";
import { ArrowRight, CompareIcon, HeartIcon, SearchIcon, SparkIcon, UserIcon, WalletIcon } from "@/components/icons";

const FACTS = [
  ["4", "sources searched in parallel"],
  ["Every store", "price for the pick, re-read from the page"],
  ["Remembers", "your taste across sessions"],
  ["Asks first", "when it’s a genuine close call"],
];

const STEPS = [
  ["01", "Tell Barney what you need", "A few targeted questions about budget, use and taste. Never a form, never twenty of them."],
  ["02", "He searches everywhere", "Google Shopping and the wider web at once, then filters out stale, wrong-spec and junk listings."],
  ["03", "You get one clear pick", "A recommendation with the reasons, every store’s price, and a side-by-side if you want to compare."],
];

const FEATURES = [
  { Icon: SearchIcon, title: "Asks the right questions", text: "Understands what you need, not just keywords.", chips: ["Budget?", "Daily use?", "Brand to avoid?"] },
  { Icon: UserIcon, title: "Remembers what matters", text: "Your preferences and budget, across sessions. Edit or forget anything.", chips: ["Prefers over-ear", "Budget ₹5k", "Likes minimal"] },
  { Icon: CompareIcon, title: "Compares with context", text: "Real listings side by side, with a verdict on what fits you and why.", chips: ["Specs", "Budget check", "Verdict"] },
  { Icon: WalletIcon, title: "Prices you can trust", text: "Reads prices from store pages and links to the cheapest reliable seller. Unverified prices are labelled." },
  { Icon: SparkIcon, title: "Speaks up on close calls", text: "When cheaper and better-rated are a real trade-off, Barney pauses and lets you choose." },
  { Icon: HeartIcon, title: "Keeps you on track", text: "A wishlist, a monthly budget and price drops, so you buy at the right time." },
];

export default function Landing() {
  return (
    <div className="overflow-x-clip">
      <Nav />

      <main>
        {/* hero */}
        <section className="relative">
          <div aria-hidden className="hero-bg pointer-events-none absolute inset-0" />
          <div className="relative mx-auto w-full max-w-[1120px] px-6 pb-20 pt-16 text-center md:px-10 md:pt-24">
            <p className="inline-flex items-center gap-2 rounded-full border border-line bg-card/80 px-3.5 py-1.5 text-[12px] font-medium uppercase tracking-[0.14em] text-muted">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-amber" /> Your wingman for buying things
            </p>
            <h1 className="mx-auto mt-8 max-w-[14ch] font-serif text-[54px] font-normal leading-[1.02] tracking-[-0.03em] sm:text-[84px] md:max-w-[16ch] md:text-[96px]">
              It’s gonna be legen<span className="wait">… wait for it …</span><span className="dary">dary.</span>
            </h1>
            <p className="mx-auto mt-8 max-w-[34rem] text-[18px] leading-8 text-muted">
              Tell Barney what you’re after. He’ll find the options, compare the prices, and help you make a choice worthy of the story.
            </p>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <Link href="/app" className="inline-flex items-center gap-2 rounded-full bg-ink px-7 py-3.5 text-[15px] text-white transition-colors hover:bg-ink/85">
                Start shopping <ArrowRight width={17} height={17} />
              </Link>
              <a href="#how" className="rounded-full border border-line-strong bg-card px-7 py-3.5 text-[15px] transition-colors hover:border-ink/40">See how it works</a>
            </div>
            <div className="mt-16">
              <LandingSearch />
            </div>
          </div>
        </section>

        {/* facts */}
        <section aria-label="What Barney does" className="border-y border-line bg-sidebar/60">
          <dl className="mx-auto grid w-full max-w-[1120px] grid-cols-2 gap-px px-6 py-10 md:grid-cols-4 md:px-10">
            {FACTS.map(([big, small]) => (
              <div key={big} className="px-2 py-3 text-center md:px-6">
                <dt className="font-serif text-[28px] leading-none tracking-[-0.01em]">{big}</dt>
                <dd className="mx-auto mt-2 max-w-[16ch] text-[13px] leading-5 text-muted">{small}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* product peek */}
        <section className="mx-auto w-full max-w-[1120px] px-6 py-28 md:px-10">
          <Reveal className="mx-auto max-w-[40rem] text-center">
            <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-muted">The answer, not a list</p>
            <h2 className="mt-4 font-serif text-[40px] leading-[1.08] tracking-[-0.02em] sm:text-[52px]">One pick. Every store’s price. The reasons why.</h2>
          </Reveal>
          <Reveal className="mt-14" delay={80}>
            <ProductPeek />
          </Reveal>
        </section>

        {/* how it works */}
        <section id="how" className="scroll-mt-20 border-t border-line">
          <div className="mx-auto w-full max-w-[1120px] px-6 py-28 md:px-10">
            <Reveal>
              <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-muted">How it works</p>
              <h2 className="mt-4 max-w-[18ch] font-serif text-[40px] leading-[1.08] tracking-[-0.02em] sm:text-[52px]">Three steps to a legendary buy.</h2>
            </Reveal>
            <ol className="mt-14 grid gap-5 md:grid-cols-3">
              {STEPS.map(([n, title, text], i) => (
                <li key={n}>
                  <Reveal delay={i * 90} className="h-full">
                    <div className="elev h-full rounded-3xl border border-line bg-card p-8">
                      <span className="font-serif text-[40px] leading-none text-line-strong">{n}</span>
                      <h3 className="mt-8 text-[18px] font-medium tracking-[-0.005em]">{title}</h3>
                      <p className="mt-2.5 text-[14.5px] leading-7 text-muted">{text}</p>
                    </div>
                  </Reveal>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* features */}
        <section id="features" className="scroll-mt-20 border-t border-line bg-sidebar/50">
          <div className="mx-auto w-full max-w-[1120px] px-6 py-28 md:px-10">
            <Reveal className="max-w-[40rem]">
              <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-muted">More than a search bar</p>
              <h2 className="mt-4 font-serif text-[40px] leading-[1.08] tracking-[-0.02em] sm:text-[52px]">A shopping assistant that gets you.</h2>
            </Reveal>
            <div className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map(({ Icon, title, text, chips }, i) => (
                <Reveal key={title} delay={(i % 3) * 80}>
                  <article className="elev flex h-full flex-col rounded-3xl border border-line bg-card p-8 transition-transform duration-300 hover:-translate-y-0.5">
                    <span className="grid h-11 w-11 place-items-center rounded-xl bg-tint text-ink"><Icon /></span>
                    <h3 className="mt-6 text-[17px] font-medium tracking-[-0.005em]">{title}</h3>
                    <p className="mt-2 text-[14.5px] leading-7 text-muted">{text}</p>
                    {chips && (
                      <ul className="mt-6 flex flex-wrap gap-2" aria-hidden>
                        {chips.map((c) => <li key={c} className="rounded-full border border-line bg-paper px-3 py-1 text-[12px] text-muted">{c}</li>)}
                      </ul>
                    )}
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* the code */}
        <section id="code" className="scroll-mt-20 bg-ink text-paper">
          <div className="mx-auto w-full max-w-[1120px] px-6 py-28 text-center md:px-10">
            <Reveal>
              <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-white/50">The Barney code</p>
              <blockquote className="mx-auto mt-8 max-w-[26ch] font-serif text-[38px] leading-[1.12] tracking-[-0.02em] sm:text-[54px]">
                “The best things in life aren’t things. But the right things are.”
              </blockquote>
              <p className="mx-auto mt-8 max-w-[32rem] text-[16px] leading-8 text-white/60">
                Barney remembers what you like, checks prices across stores, and makes sure you never overpay. Because you’re awesome, and so are your purchases.
              </p>
            </Reveal>
          </div>
        </section>

        {/* final cta */}
        <section className="mx-auto w-full max-w-[1120px] px-6 py-28 text-center md:px-10">
          <Reveal>
            <h2 className="mx-auto max-w-[16ch] font-serif text-[44px] leading-[1.05] tracking-[-0.02em] sm:text-[64px]">
              Challenge accepted<span className="text-faint">?</span>
            </h2>
            <p className="mx-auto mt-6 max-w-[28rem] text-[17px] leading-8 text-muted">Free to start. Sign in to keep your wishlist, budget and preferences.</p>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <Link href="/app" className="inline-flex items-center gap-2 rounded-full bg-ink px-7 py-3.5 text-[15px] text-white transition-colors hover:bg-ink/85">
                Start shopping <ArrowRight width={17} height={17} />
              </Link>
              <Link href="/signin" className="rounded-full border border-line-strong bg-card px-7 py-3.5 text-[15px] transition-colors hover:border-ink/40">Sign in</Link>
            </div>
          </Reveal>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-[1120px] flex-wrap items-center justify-between gap-4 px-6 py-8 text-[13px] text-faint md:px-10">
          <Logo className="text-[22px] leading-none" />
          <nav aria-label="Footer" className="flex gap-6">
            <Link href="/app" className="transition-colors hover:text-ink">Start shopping</Link>
            <Link href="/signin" className="transition-colors hover:text-ink">Sign in</Link>
          </nav>
          <span>Built for smart shoppers in India</span>
        </div>
      </footer>
    </div>
  );
}
