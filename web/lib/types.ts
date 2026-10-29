export type Store = {
  name: string;
  price_inr: number;
  price_display: string;
  link: string;
  trusted: boolean;
  verified: boolean | "corrected" | null;
  tag?: string | null;
  shipping?: string | null;
  total_inr?: number | null;
  delivery?: string | null;
  offers?: string[];
};

export type Offer = {
  number: number;
  title: string;
  price_display: string;
  price_inr?: number | null;
  price_verified?: boolean;
  seller: string;
  seller_trusted?: boolean;
  link?: string | null;
  link_domain?: string | null;
  image_url?: string | null;
  rating?: number | null;
  rating_count?: number | null;
  best?: boolean;
  token?: string | null;
  product?: string;
  stores?: Store[];
  over_budget?: boolean;
  notes?: Note[];
  checked_at?: number | null;
};

export type Note = { kind: "good" | "warn"; text: string };

export type TableRow = Offer & {
  year?: number | null;
  values: Record<string, string | null>;
  matches: Record<string, "yes" | "no" | "unknown">;
};

export type CompareTable = { specs: string[]; requirements: string[]; rows: TableRow[] };

export type FormQuestion = { topic: string; question: string; options: string[]; durable?: boolean };
export type Form = { questions: FormQuestion[] };

export type Turn = {
  role: "user" | "assistant";
  content: string;
  products?: Offer[];
  options?: string[];
  table?: CompareTable | null;
  form?: Form | null;
};

export type WishItem = {
  id: number;
  product: string;
  title: string;
  price_display?: string;
  price_inr?: number | null;
  seller?: string;
  link?: string | null;
  image_url?: string | null;
  target_inr?: number | null;
  price_low?: number;
  price_high?: number;
  checks?: number;
  checked_at?: number;
};

export type PriceAlert = { id: number; wishlist_id: number; title: string; price_inr: number; target_inr: number; link?: string | null; at: number };

export type ComparisonCard = {
  thread_id: string;
  title: string;
  image_url?: string | null;
  options: number;
  price_low?: number | null;
  price_high?: number | null;
  rating?: number | null;
  rating_count?: number | null;
  stores: number;
  tag: string;
  specs: string[];
};

export type Budget = { amount: number | null; wishlist_total: number; remaining: number | null };

export type Overview = {
  name: string | null;
  stats: { wishlist: number; comparisons: number; preferences: number };
  budget: Budget;
  wishlist: WishItem[];
  comparisons: ComparisonCard[];
  alerts?: number;
};

export type Memory = { key: string; text: string; category: string; source: "said" | "inferred" };
export type Suggestion = { id: number; text: string; category: string };
export type Settings = { learning: boolean; onboarded: boolean; profiles: string[] };
export type ReviewSummary = {
  rating?: number | null;
  count?: number | null;
  split: { stars: number; percent: number }[];
  praise: string[];
  complaints: string[];
  verdict: string;
};
export type SharedComparison = { title: string; table: CompareTable };

export type StreamEvent =
  | { type: "status"; text: string }
  | { type: "preview"; products: Offer[] }
  | { type: "done"; answer: ChatResponse };

export type ChatResponse = {
  reply: string;
  options?: string[];
  products?: Offer[];
  table?: CompareTable | null;
  form?: Form | null;
};
