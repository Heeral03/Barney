import type { Budget, ChatResponse, ComparisonCard, Memory, Offer, Overview, Store, Turn, WishItem } from "./types";

// `/api/*` is proxied to the Barney back end by next.config.ts.
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
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
  chat: (message: string, thread_id: string, user_id: string) =>
    call<ChatResponse>("/chat", json("POST", { message, thread_id, user_id })),
  history: (thread_id: string, user_id: string) => call<Turn[]>(`/history${q({ thread_id, user_id })}`),
  overview: (user_id: string) => call<Overview>(`/overview${q({ user_id })}`),
  comparisons: (user_id: string, limit = 12) => call<ComparisonCard[]>(`/comparisons${q({ user_id, limit })}`),

  wishlist: (user_id: string) => call<WishItem[]>(`/wishlist${q({ user_id })}`),
  addWish: (user_id: string, offer: Offer, product: string) =>
    call<{ id: number | null; new: boolean }>("/wishlist", json("POST", { user_id, offer, product })),
  removeWish: (user_id: string, id: number) => call<{ ok: boolean }>(`/wishlist/${id}${q({ user_id })}`, { method: "DELETE" }),
  setTarget: (user_id: string, id: number, target_inr: number | null) =>
    call<{ ok: boolean }>(`/wishlist/${id}/target`, json("PUT", { user_id, target_inr })),

  budget: (user_id: string) => call<Budget>(`/budget${q({ user_id })}`),
  setBudget: (user_id: string, amount_inr: number | null) => call<Budget>("/budget", json("PUT", { user_id, amount_inr })),

  memories: (user_id: string) => call<Memory[]>(`/memories${q({ user_id })}`),
  forget: (user_id: string, key: string) => call<{ ok: boolean }>(`/memories/${key}${q({ user_id })}`, { method: "DELETE" }),

  compare: (token: string) =>
    call<{ stores: Store[]; cheapest: Partial<Offer> | null; text: string }>("/compare", json("POST", { token })),
};
