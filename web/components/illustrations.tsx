import type { SVGProps } from "react";

/** Quiet line illustrations for the popular-search cards (no photos, so nothing to license or break). */
const stroke = "#8b857b";
const fill = "#ebe7e0";
const dark = "#d9d4ca";

function Art({ children, ...p }: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 120 90" fill="none" stroke={stroke} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden {...p}>
      {children}
    </svg>
  );
}

export const Headphones = (p: SVGProps<SVGSVGElement>) => (
  <Art {...p}>
    <path d="M28 56V46a32 32 0 0 1 64 0v10" />
    <rect x="20" y="52" width="16" height="26" rx="8" fill={fill} />
    <rect x="84" y="52" width="16" height="26" rx="8" fill={fill} />
    <path d="M28 60v10M92 60v10" stroke={dark} />
  </Art>
);

export const Laptop = (p: SVGProps<SVGSVGElement>) => (
  <Art {...p}>
    <rect x="25" y="18" width="70" height="46" rx="4" fill={fill} />
    <rect x="30" y="23" width="60" height="36" rx="2" fill="#f7f5f1" />
    <path d="M14 70h92l-6 8H20l-6-8Z" fill={fill} />
    <path d="M52 74h16" stroke={dark} />
  </Art>
);

export const Backpack = (p: SVGProps<SVGSVGElement>) => (
  <Art {...p}>
    <path d="M48 24c0-8 24-8 24 0" />
    <path d="M36 34c0-8 6-12 24-12s24 4 24 12v40c0 4-3 7-7 7H43c-4 0-7-3-7-7V34Z" fill={fill} />
    <rect x="46" y="54" width="28" height="18" rx="4" fill="#f7f5f1" />
    <path d="M46 40h28M60 54v6" stroke={dark} />
  </Art>
);

export const Sneaker = (p: SVGProps<SVGSVGElement>) => (
  <Art {...p}>
    <path d="M14 60c0-4 3-6 7-7l16-3 8-14c3 1 6 4 10 6 6 3 14 4 24 6 12 2 22 6 22 14v4H14v-6Z" fill={fill} />
    <path d="M14 66h92v6c0 2-2 4-4 4H18c-2 0-4-2-4-4v-6Z" fill="#f7f5f1" />
    <path d="M52 40l6 4M60 46l6 3M38 50l12 2" stroke={dark} />
  </Art>
);

export const Tag = (p: SVGProps<SVGSVGElement>) => (
  <Art {...p}>
    <path d="M18 50 52 16h36v36L54 86 18 50Z" fill={fill} />
    <circle cx="74" cy="34" r="5" fill="#f7f5f1" />
  </Art>
);

/** An illustration chosen from a product name, for when there is no photo. */
export function ArtFor({ text, ...p }: { text: string } & SVGProps<SVGSVGElement>) {
  const t = text.toLowerCase();
  if (/headphone|earbud|earphone|airpod|speaker/.test(t)) return <Headphones {...p} />;
  if (/laptop|macbook|notebook|computer/.test(t)) return <Laptop {...p} />;
  if (/bag|backpack|rucksack/.test(t)) return <Backpack {...p} />;
  if (/shoe|sneaker|runner|boot|sandal/.test(t)) return <Sneaker {...p} />;
  return <Tag {...p} />;
}
