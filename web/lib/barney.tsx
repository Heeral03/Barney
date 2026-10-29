"use client";

import { useSession } from "next-auth/react";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setActiveProfile } from "./api";
import { newId, wishKey } from "./format";
import type { Offer, Overview, Settings, Turn, WishItem } from "./types";

type Barney = {
  ready: boolean;
  /** The signed-in Google account, or null for a guest. */
  account: { name?: string | null; email?: string | null; image?: string | null } | null;
  turns: Turn[];
  sending: boolean;
  /** While a reply is being worked out: what Barney is doing now, and the candidates found so far. */
  progress: { status: string; preview: Offer[] };
  hasHistory: boolean;
  overview: Overview | null;
  wishlist: WishItem[];
  isWished: (offer: { link?: string | null; title?: string }) => boolean;
  send: (text: string, answers?: Record<string, string[]>) => Promise<void>;
  newChat: () => void;
  openThread: (threadId: string) => Promise<void>;
  resume: () => Promise<void>;
  toggleWish: (offer: Offer) => Promise<void>;
  refresh: () => Promise<void>;
  /** Account settings (learning on/off, onboarding done, shopping profiles) and the profile Barney is shopping for. */
  settings: Settings | null;
  refreshSettings: () => Promise<void>;
  profile: string;
  setProfile: (name: string) => void;
};

const Ctx = createContext<Barney | null>(null);
const THREAD_KEY = "barney_thread";
const PROFILE_KEY = "barney_profile";

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
  const { data: session, status } = useSession();
  const account = session?.user ?? null;
  const [threadId, setThreadId] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sending, setSending] = useState(false);
  const [progress, setProgress] = useState<{ status: string; preview: Offer[] }>({ status: "", preview: [] });
  const [hasHistory, setHasHistory] = useState(false);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [wishlist, setWishlist] = useState<WishItem[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [profile, setProfileState] = useState("me");

  const refreshSettings = useCallback(async () => {
    setSettings(await api.settings().catch(() => null));
  }, []);

  const setProfile = useCallback((name: string) => {
    setActiveProfile(name);
    write(PROFILE_KEY, name);
    setProfileState(name);
  }, []);

  const refresh = useCallback(async () => {
    const [o, w] = await Promise.allSettled([api.overview(), api.wishlist()]);
    if (o.status === "fulfilled") setOverview(o.value);
    if (w.status === "fulfilled") setWishlist(w.value);
  }, []);

  // Who the shopper is comes from the sign-in session on the server, never from this page. Only the current conversation's
  // id lives in this browser. Once the session is known (guest or Google), load their data; right after signing in,
  // first bring over what they did as a guest.
  useEffect(() => {
    if (status === "loading") return;
    let live = true;
    (async () => {
      const tid = read(THREAD_KEY) || `web-${newId()}`;
      write(THREAD_KEY, tid);
      const saved = read(PROFILE_KEY) || "me";
      setActiveProfile(saved);
      setProfileState(saved);
      if (status === "authenticated") await api.claimGuest().catch(() => {});
      if (!live) return;
      setThreadId(tid);
      setReady(true);
      refresh();
      refreshSettings();
      api.history(tid).then((h) => live && setHasHistory(h.length > 0)).catch(() => {});
    })();
    return () => { live = false; };
  }, [status, refresh, refreshSettings]);

  const send = useCallback(async (text: string, answers?: Record<string, string[]>) => {
    const message = text.trim();
    if (!message || sending || !ready) return;
    setTurns((t) => [...t, { role: "user", content: message }]);
    setSending(true);
    try {
      setProgress({ status: "Thinking…", preview: [] });
      const r = await api.chatStream(message, threadId, answers, (e) => {
        if (e.type === "status") setProgress((p) => ({ ...p, status: e.text }));
        if (e.type === "preview") setProgress((p) => ({ ...p, preview: e.products }));
      });
      setTurns((t) => [...t, { role: "assistant", content: r.reply, products: r.products, options: r.options, table: r.table, form: r.form }]);
    } catch {
      setTurns((t) => [...t, { role: "assistant", content: "I couldn't reach the server. Is the Barney back end running?" }]);
    } finally {
      setSending(false);
      setProgress({ status: "", preview: [] });
      setHasHistory(true);
      refresh();
    }
  }, [sending, ready, threadId, refresh]);

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
    setTurns(await api.history(id).catch(() => []));
  }, []);

  const resume = useCallback(() => openThread(threadId), [openThread, threadId]);

  const isWished = useCallback((o: { link?: string | null; title?: string }) => wishlist.some((w) => wishKey(w) === wishKey(o)), [wishlist]);

  const toggleWish = useCallback(async (offer: Offer) => {
    const existing = wishlist.find((w) => wishKey(w) === wishKey(offer));
    if (existing) await api.removeWish(existing.id);
    else await api.addWish(offer, offer.product ?? "");
    await refresh();
  }, [wishlist, refresh]);

  return (
    <Ctx.Provider value={{ ready, account, turns, sending, progress, hasHistory, overview, wishlist, isWished, send, newChat, openThread, resume, toggleWish, refresh, settings, refreshSettings, profile, setProfile }}>
      {children}
    </Ctx.Provider>
  );
}

export function useBarney(): Barney {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useBarney must be used inside <BarneyProvider>");
  return ctx;
}
