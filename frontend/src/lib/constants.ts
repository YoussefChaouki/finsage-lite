/**
 * FinSage-Lite — Application-wide constants
 *
 * Section colour maps mirror the design system in SPRINT5_CADRAGE.md.
 * All Tailwind classes must be complete strings (no dynamic construction)
 * so the JIT compiler includes them in the bundle.
 */

import type { SectionType } from "@/lib/types";

export const APP_NAME = "FinSage-Lite" as const;

export const API_BASE_URL = "";

/** React Query refetch interval for the /health polling (ms). */
export const POLLING_INTERVAL = 10_000;

// ─── Section colours ─────────────────────────────────────────────────────────

export interface SectionStyle {
  /** Tailwind bg + border + text classes for the badge */
  badge: string;
  /** Tailwind border colour for section cards */
  border: string;
  /** Dot / accent colour used in inline indicators */
  dot: string;
}

export const SECTION_COLORS: Record<SectionType, SectionStyle> = {
  ITEM_1: {
    badge: "bg-sky-500/10 border-sky-500/50 text-sky-400",
    border: "border-sky-500/50",
    dot: "bg-sky-500",
  },
  ITEM_1A: {
    badge: "bg-red-500/10 border-red-500/50 text-red-400",
    border: "border-red-500/50",
    dot: "bg-red-500",
  },
  ITEM_7: {
    badge: "bg-emerald-500/10 border-emerald-500/50 text-emerald-400",
    border: "border-emerald-500/50",
    dot: "bg-emerald-500",
  },
  ITEM_7A: {
    badge: "bg-orange-500/10 border-orange-500/50 text-orange-400",
    border: "border-orange-500/50",
    dot: "bg-orange-500",
  },
  ITEM_8: {
    badge: "bg-violet-500/10 border-violet-500/50 text-violet-400",
    border: "border-violet-500/50",
    dot: "bg-violet-500",
  },
  OTHER: {
    badge: "bg-slate-700/10 border-slate-600/50 text-slate-400",
    border: "border-slate-600/50",
    dot: "bg-slate-500",
  },
};

export const SECTION_LABELS: Record<SectionType, string> = {
  ITEM_1: "Business",
  ITEM_1A: "Risk Factors",
  ITEM_7: "MD&A",
  ITEM_7A: "Market Risk",
  ITEM_8: "Financials",
  OTHER: "Other",
};
