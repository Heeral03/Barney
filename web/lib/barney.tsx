"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import { newId, wishKey } from "./format";
import type { Offer, Overview, Turn, WishItem } from "./types";

type Barney = {
  ready: boolean;
  userId: string;
  setUserId: (id: string) => void;
  turns: Turn[];
  sending: boolean;
  hasHistory: boolean;
  overview: Overview | null;
  wishlist: WishItem[];
  isWished: (offer: { link?: string | null; title?: string }) => boolean;
  send: (text: string) => Promise<void>;
  newChat: () => void;
  openThread: (threadId: string) => Promise<void>;
  resume: () => Promise<void>;
  toggleWish: (offer: Offer) => Promise<void>;
  refresh: () => Promise<void>;
};

const Ctx = createContext<Barney | null>(null);
const USER_KEY = "barney_user";
const THREAD_KEY = "barney_thread";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {}
}

export function BarneyProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [userId, setUserIdState] = useState("");
  const [threadId, setThreadId] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sending, setSending] = useState(false);
  const [hasHistory, setHasHistory] = useState(false);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [wishlist, setWishlist] = useState<WishItem[]>([]);

  const refreshFor = useCallback(async (uid: string) => {
    const [o, w] = await Promise.allSettled([api.overview(uid), api.wishlist(uid)]);
    if (o.status === "fulfilled") setOverview(o.value);
    if (w.status === "fulfilled") setWishlist(w.value);
  }, []);

  // The shopper's id and the current conversation live in this browser; the memories behind them live on the server.
  // Reading localStorage must wait for the browser (the server render has none), so this is set once after mount.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const uid = read(USER_KEY) || `u-web-${newId()}`;
    const tid = read(THREAD_KEY) || `web-${newId()}`;
    write(USER_KEY, uid);
    write(THREAD_KEY, tid);
    setUserIdState(uid);
    setThreadId(tid);
    setReady(true);
    refreshFor(uid);
    api.history(tid, uid).then((h) => setHasHistory(h.length > 0)).catch(() => {});
  }, [refreshFor]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const refresh = useCallback(async () => {
    if (userId) await refreshFor(userId);
  }, [userId, refreshFor]);

  const setUserId = useCallback((id: string) => {
    const clean = id.trim();
    if (!clean) return;
    write(USER_KEY, clean);
    setUserIdState(clean);
    setTurns([]);
    refreshFor(clean);
  }, [refreshFor]);

  const send = useCallback(async (text: string) => {
    const message = text.trim();
    if (!message || sending || !userId) return;
    setTurns((t) => [...t, { role: "user", content: message }]);
    setSending(true);
    try {
      const r = await api.chat(message, threadId, userId);
      setTurns((t) => [...t, { role: "assistant", content: r.reply, products: r.products, options: r.options, table: r.table }]);
    } catch {
      setTurns((t) => [...t, { role: "assistant", content: "I couldn't reach the server. Is the Barney back end running?" }]);
    } finally {
      setSending(false);
      setHasHistory(true);
      refreshFor(userId);
    }
  }, [sending, userId, threadId, refreshFor]);

  const newChat = useCallback(() => {
    const tid = `web-${newId()}`;
    write(THREAD_KEY, tid);
    setThreadId(tid);
    setTurns([]);
    setHasHistory(false);
  }, []);

  const openThread = useCallback(async (id: string) => {
    write(THREAD_KEY, id);
    setThreadId(id);
    setTurns(await api.history(id, userId).catch(() => []));
  }, [userId]);

  const resume = useCallback(() => openThread(threadId), [openThread, threadId]);

  const isWished = useCallback((o: { link?: string | null; title?: string }) => wishlist.some((w) => wishKey(w) === wishKey(o)), [wishlist]);

  const toggleWish = useCallback(async (offer: Offer) => {
    if (!userId) return;
    const existing = wishlist.find((w) => wishKey(w) === wishKey(offer));
    if (existing) await api.removeWish(userId, existing.id);
    else await api.addWish(userId, offer, offer.product ?? "");
    await refreshFor(userId);
  }, [userId, wishlist, refreshFor]);

  return (
    <Ctx.Provider value={{ ready, userId, setUserId, turns, sending, hasHistory, overview, wishlist, isWished, send, newChat, openThread, resume, toggleWish, refresh }}>
      {children}
    </Ctx.Provider>
  );
}

export function useBarney(): Barney {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useBarney must be used inside <BarneyProvider>");
  return ctx;
}
