export type Store = {
  name: string;
  price_inr: number;
  price_display: string;
  link: string;
  trusted: boolean;
  verified: boolean | "corrected" | null;
  tag?: string | null;
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
};

export type TableRow = Offer & {
  values: Record<string, string | null>;
  matches: Record<string, "yes" | "no" | "unknown">;
};

export type CompareTable = { specs: string[]; requirements: string[]; rows: TableRow[] };

export type Turn = {
  role: "user" | "assistant";
  content: string;
  products?: Offer[];
  options?: string[];
  table?: CompareTable | null;
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
};

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
};

export type Memory = { key: string; text: string; category: string };

export type ChatResponse = {
  reply: string;
  options?: string[];
  products?: Offer[];
  table?: CompareTable | null;
};
