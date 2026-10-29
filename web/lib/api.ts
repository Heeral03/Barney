import type { Budget, ChatResponse, CompareTable, PriceAlert, ReviewSummary, Settings, SharedComparison, StreamEvent, Suggestion, ComparisonCard, Memory, Offer, Overview, Store, Turn, WishItem } from "./types";

// `/api/*` is forwarded to the Barney back end by app/api/[...path]/route.ts, which adds who is calling.
// The shopping profile ("me", "Mom"...) is only a label inside the signed-in account; the back end checks it.
let profile = "me";
export const setActiveProfile = (name: string) => { profile = name; };
const withProfile = (init: RequestInit = {}): RequestInit => ({ ...init, headers: { ...(init.headers as Record<string, string>), "x-barney-profile": profile } });

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, withProfile(init));
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const q = (params: Record<string, string | number>) =>
  "?" + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();

export const api = {
  chat: (message: string, thread_id: string, answers?: Record<string, string[]>) =>
    call<ChatResponse>("/chat", json("POST", { message, thread_id, answers })),
  /** The same turn as `chat`, but progress arrives while it runs: a status line, the candidates, then the full answer. */
  chatStream: async (message: string, thread_id: string, answers: Record<string, string[]> | undefined, onEvent: (e: StreamEvent) => void) => {
    const res = await fetch("/api/chat/stream", withProfile(json("POST", { message, thread_id, answers })));
    if (!res.ok || !res.body) throw new Error(`/chat/stream: ${res.status}`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffered = "";
    let done: ChatResponse | null = null;
    for (;;) {
      const { value, done: finished } = await reader.read();
      buffered += decoder.decode(value, { stream: !finished });
      const lines = buffered.split("\n");
      buffered = lines.pop() ?? "";
      for (const line of lines.filter(Boolean)) {
        const event = JSON.parse(line) as StreamEvent;
        if (event.type === "done") done = event.answer;
        onEvent(event);
      }
      if (finished) break;
    }
    if (!done) throw new Error("the reply ended early");
    return done;
  },
  history: (thread_id: string) => call<Turn[]>(`/history${q({ thread_id })}`),
  overview: () => call<Overview>("/overview"),
  comparisons: (limit = 12) => call<ComparisonCard[]>(`/comparisons${q({ limit })}`),

  wishlist: () => call<WishItem[]>("/wishlist"),
  addWish: (offer: Offer, product: string) =>
    call<{ id: number | null; new: boolean }>("/wishlist", json("POST", { offer, product })),
  checkPrice: (id: number) => call<{ price: number | null; alert: boolean; checked_at: number }>(`/wishlist/${id}/check`, { method: "POST" }),
  alerts: () => call<PriceAlert[]>("/alerts"),
  alertsSeen: () => call<{ ok: boolean }>("/alerts/seen", { method: "POST" }),
  removeWish: (id: number) => call<{ ok: boolean }>(`/wishlist/${id}`, { method: "DELETE" }),
  setTarget: (id: number, target_inr: number | null) =>
    call<{ ok: boolean }>(`/wishlist/${id}/target`, json("PUT", { target_inr })),

  budget: () => call<Budget>("/budget"),
  setBudget: (amount_inr: number | null) => call<Budget>("/budget", json("PUT", { amount_inr })),

  memories: () => call<Memory[]>("/memories"),
  editMemory: (key: string, text: string) => call<{ ok: boolean }>(`/memories/${key}`, json("PUT", { text })),
  suggestions: () => call<Suggestion[]>("/suggestions"),
  decide: (id: number, decision: "accept" | "dismiss") => call<{ ok: boolean }>(`/suggestions/${id}/${decision}`, { method: "POST" }),
  settings: () => call<Settings>("/settings"),
  setLearning: (learning: boolean) => call<Settings>("/settings", json("PUT", { learning })),
  addProfile: (name: string) => call<Settings>("/profiles", json("POST", { name })),
  removeProfile: (name: string) => call<Settings>(`/profiles/${encodeURIComponent(name)}`, { method: "DELETE" }),
  onboarding: (categories: string[], priority: string, spend: string) => call<Settings>("/onboarding", json("POST", { categories, priority, spend })),
  event: (kind: "open" | "compare_store", product: string, title: string) => call<{ recorded: boolean }>("/events", json("POST", { kind, product, title })).catch(() => {}),
  feedback: (title: string, product: string, verdict: "up" | "down" | "wrong", thread_id = "") => call<{ ok: boolean }>("/feedback", json("POST", { title, product, verdict, thread_id })),
  track: (name: string) => call<{ ok: boolean }>("/track", json("POST", { name })).catch(() => {}),
  reviewSummary: (token: string) => call<ReviewSummary>("/reviews/summary", json("POST", { token })),
  share: (title: string, table: CompareTable) => call<{ id: string }>("/share", json("POST", { title, table })),
  shared: (id: string) => call<SharedComparison>(`/share/${encodeURIComponent(id)}`),
  forget: (key: string) => call<{ ok: boolean }>(`/memories/${key}`, { method: "DELETE" }),

  // After sign-in: bring over what this browser did as a guest.
  claimGuest: () => call<{ claimed: boolean }>("/me/claim-guest", json("POST", {})),

  compare: (token: string) =>
    call<{ stores: Store[]; cheapest: Partial<Offer> | null; text: string }>("/compare", json("POST", { token })),
};
