/** ₹1,23,456: Indian digit grouping. */
export function inr(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "";
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

/** 8200 -> "8.2k" */
export function compact(n: number | null | undefined): string {
  if (!n) return "0";
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, "")}k` : String(n);
}

export function priceRange(low?: number | null, high?: number | null): string {
  if (!low) return "";
  return !high || high === low ? inr(low) : `${inr(low)} – ${inr(high)}`;
}

export function greeting(date = new Date()): string {
  const h = date.getHours();
  return h < 5 ? "Good evening" : h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export function initials(name: string | null | undefined): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  return (parts.length ? parts.slice(0, 2).map((p) => p[0]).join("") : "B").toUpperCase();
}

export function newId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

/** "5 min ago" for a time in epoch seconds. */
export function ago(epochSeconds: number | null | undefined): string {
  if (!epochSeconds) return "";
  const minutes = Math.max(0, Math.floor((Date.now() / 1000 - epochSeconds) / 60));
  return minutes < 1 ? "just now" : minutes < 60 ? `${minutes} min ago` : minutes < 1440 ? `${Math.floor(minutes / 60)} h ago` : `${Math.floor(minutes / 1440)} d ago`;
}

/** What a listing is called in the wishlist: its link, else its title. */
export function wishKey(o: { link?: string | null; title?: string }): string {
  return (o.link || o.title || "").toLowerCase();
}
