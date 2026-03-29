/**
 * FinSage-Lite — Global Zustand store
 *
 * Holds the search/filter state shared across the Search and Browse pages.
 */

import { create } from "zustand";
import type { SearchMode } from "@/lib/types";

interface AppState {
  selectedCompany: string | null;
  selectedYear: number | null;
  selectedMode: SearchMode;
  hydeEnabled: boolean;

  setCompany: (company: string | null) => void;
  setYear: (year: number | null) => void;
  setMode: (mode: SearchMode) => void;
  toggleHyde: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedCompany: null,
  selectedYear: null,
  selectedMode: "hybrid",
  hydeEnabled: false,

  setCompany: (company) => set({ selectedCompany: company }),
  setYear: (year) => set({ selectedYear: year }),
  setMode: (mode) => set({ selectedMode: mode }),
  toggleHyde: () => set((s) => ({ hydeEnabled: !s.hydeEnabled })),
}));
