import type { ReactNode, SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

function Icon({ children, ...p }: P & { children: ReactNode }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden {...p}>
      {children}
    </svg>
  );
}

export const SearchIcon = (p: P) => <Icon {...p}><circle cx="11" cy="11" r="6.5" /><path d="m20 20-3.6-3.6" /></Icon>;
export const HeartIcon = ({ filled, ...p }: P & { filled?: boolean }) => (
  <Icon {...p} fill={filled ? "currentColor" : "none"}><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10Z" /></Icon>
);
export const CalendarIcon = (p: P) => <Icon {...p}><rect x="4" y="5.5" width="16" height="14" rx="2.5" /><path d="M8 3.5v4M16 3.5v4M4 10h16" /></Icon>;
export const UserIcon = (p: P) => <Icon {...p}><circle cx="12" cy="8.5" r="3.5" /><path d="M5 20c.8-3.6 3.5-5.5 7-5.5s6.2 1.9 7 5.5" /></Icon>;
export const BellIcon = (p: P) => <Icon {...p}><path d="M6 16.5V11a6 6 0 1 1 12 0v5.5l1.5 1.5h-15L6 16.5Z" /><path d="M10 20.5a2.2 2.2 0 0 0 4 0" /></Icon>;
export const ArrowRight = (p: P) => <Icon {...p}><path d="M5 12h14M13 6l6 6-6 6" /></Icon>;
export const ArrowUp = (p: P) => <Icon {...p}><path d="M12 19V5M6 11l6-6 6 6" /></Icon>;
export const GearIcon = (p: P) => (
  <Icon {...p}><circle cx="12" cy="12" r="3" /><path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" /></Icon>
);
export const SunIcon = (p: P) => <Icon {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.5 1.5M17.2 17.2l1.5 1.5M18.7 5.3l-1.5 1.5M6.8 17.2l-1.5 1.5" /></Icon>;
export const StarIcon = (p: P) => <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden {...p}><path d="m12 2.8 2.8 6 6.5.8-4.8 4.5 1.3 6.5L12 17.4l-5.8 3.2 1.3-6.5L2.7 9.6l6.5-.8L12 2.8Z" /></svg>;
export const CheckIcon = (p: P) => <Icon width="14" height="14" strokeWidth="2" {...p}><path d="m5 12.5 4.5 4.5L19 7.5" /></Icon>;
export const PlusIcon = (p: P) => <Icon {...p}><path d="M12 5v14M5 12h14" /></Icon>;
export const SparkIcon = (p: P) => <Icon {...p}><path d="M12 3.5 13.8 9l5.7 1.8-5.7 1.8L12 18l-1.8-5.4L4.5 10.8 10.2 9 12 3.5Z" /></Icon>;
export const WalletIcon = (p: P) => <Icon {...p}><rect x="3.5" y="6" width="17" height="13" rx="2.5" /><path d="M16 12.5h2.5M3.5 9.5h13" /></Icon>;
export const CompareIcon = (p: P) => <Icon {...p}><rect x="3.5" y="5" width="7" height="14" rx="1.8" /><rect x="13.5" y="5" width="7" height="14" rx="1.8" /></Icon>;
