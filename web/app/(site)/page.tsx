import { SignInButton, StartButton } from "@/components/LandingActions";
import { Logo } from "@/components/Sidebar";

export default function Landing() {
  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[1100px] flex-col px-6 md:px-10">
      <header className="flex items-center justify-between py-8">
        <Logo className="text-[34px] leading-none" />
        <SignInButton className="rounded-full px-4 py-2 text-[14px] text-muted transition hover:text-ink" />
      </header>

      <main className="flex flex-1 flex-col justify-center pb-24">
        <p className="text-[12px] font-medium uppercase tracking-[0.16em] text-muted">Your wingman for buying things</p>
        <h1 className="mt-6 max-w-4xl font-serif text-[52px] font-normal leading-[1.02] tracking-[-0.02em] sm:text-[76px] lg:text-[104px]">
          It’s gonna be legen<span className="text-faint">… wait for it …</span>dary.
        </h1>
        <p className="mt-8 max-w-xl text-[17px] leading-8 text-muted">
          Tell Barney what you’re after. He finds the options, compares every store’s price, and picks the one that’s actually awesome.
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <StartButton />
          <SignInButton className="rounded-full border border-line-strong px-7 py-3.5 text-[15px] text-ink/85 transition hover:bg-tint/60" />
        </div>
      </main>

      <footer className="border-t border-line py-6 text-[13px] text-faint">Barney remembers what you like, so you don’t have to repeat yourself.</footer>
    </div>
  );
}
