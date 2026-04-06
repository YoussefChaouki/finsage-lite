import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes safely, resolving conflicts. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Generate a deterministic HSL background colour from a ticker string.
 * Same ticker always produces the same colour; visually distinct palette.
 */
export function generateAvatarColor(ticker: string): string {
  let hash = 0;
  for (let i = 0; i < ticker.length; i++) {
    hash = ticker.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 55%, 32%)`;
}

/** Format an ISO date string to "Nov 2024". */
export function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-US", {
    month: "short",
    year: "numeric",
  });
}

/** Format a number with comma separators: 1234 → "1,234". */
export function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}
