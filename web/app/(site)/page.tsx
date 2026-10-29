import { LandingSearch } from "@/components/LandingSearch";
import { SignInButton } from "@/components/LandingActions";
import { Logo } from "@/components/Sidebar";

const POINTS = [
  ["Asks the right questions", "Understands what you need, not just keywords."],
  ["Remembers what matters", "Your preferences and budget, across sessions."],
  ["Compares with context", "Real listings, every store’s price, and why it fits you."],
  ["Keeps you on track", "Wishlist and price drops, so you buy at the right time."],
];

export default function Landing() {
  return (
    <div className="mx-auto w-full max-w-[1040px] px-6 md:px-10">
      <header className="flex items-center justify-between py-8">
        <Logo className="text-[30px] leading-none" />
        <SignInButton className="rounded-full px-4 py-2 text-[14px] text-muted transition hover:text-ink" />
      </header>

      <main>
        <section className="pb-16 pt-10 sm:pt-16">
          <div>
            <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-muted">Your wingman for buying things</p>
            <h1 className="mt-6 font-serif text-[48px] font-normal leading-[1.04] tracking-[-0.02em] sm:text-[68px]">
              It’s gonna be legen<span className="text-faint">… wait for it …</span>dary.
            </h1>
            <p className="mt-7 max-w-lg text-[17px] leading-8 text-muted">
              Tell Barney what you’re after. He’ll find the options, compare the prices, and help you make a choice worthy of the story.
            </p>
          </div>
        </section>

        <LandingSearch />

        <section className="mt-28 grid gap-12 border-t border-line pt-14 md:grid-cols-[1fr_1.4fr]">
          <div>
            <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-muted">More than a search bar</p>
            <h2 className="mt-4 font-serif text-[36px] font-normal leading-[1.1] tracking-[-0.01em]">A shopping assistant that gets you.</h2>
          </div>
          <dl className="grid gap-x-10 gap-y-9 sm:grid-cols-2">
            {POINTS.map(([title, text]) => (
              <div key={title}>
                <dt className="text-[15px] font-medium">{title}</dt>
                <dd className="mt-1.5 text-[14px] leading-6 text-muted">{text}</dd>
              </div>
            ))}
          </dl>
        </section>
      </main>

      <footer className="mt-28 flex flex-wrap items-center justify-between gap-3 border-t border-line py-7 text-[13px] text-faint">
        <Logo className="text-[22px] leading-none text-ink" />
        <span>“The best things in life aren’t things. But the right things are.”</span>
        <span>Built for smart shoppers in India</span>
      </footer>
    </div>
  );
}
