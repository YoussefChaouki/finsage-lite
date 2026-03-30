/**
 * SearchEmptyState — shown before the first search.
 *
 * Displays a minimal illustration, headline, and example queries
 * that pre-fill and immediately submit the search bar.
 */

import { Search } from "lucide-react";

interface SearchEmptyStateProps {
  onExampleClick: (query: string) => void;
}

const EXAMPLES = [
  "What was Apple's revenue in FY2024?",
  "Compare risk factors to previous year",
  "What are the main growth drivers?",
] as const;

export function SearchEmptyState({ onExampleClick }: SearchEmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-8 pb-12 pt-4 text-center">
      {/* Illustration */}
      <div className="relative mt-2">
        <div className="flex h-20 w-20 items-center justify-center rounded-2xl border border-slate-700/80 bg-slate-800/60 shadow-xl shadow-slate-950/50">
          <Search className="h-9 w-9 text-emerald-500/70" />
        </div>
        {/* Dollar badge */}
        <div className="absolute -bottom-2 -right-2 flex h-8 w-8 items-center justify-center rounded-full border border-slate-700 bg-slate-800">
          <span className="font-mono text-[11px] font-bold text-emerald-400">
            $
          </span>
        </div>
      </div>

      {/* Headline */}
      <div className="space-y-2">
        <h2 className="text-2xl font-bold tracking-tight text-slate-100">
          Search SEC 10-K filings with AI
        </h2>
        <p className="mx-auto max-w-sm text-sm leading-relaxed text-slate-500">
          Ask questions about annual reports, financials, and disclosures.
          Powered by hybrid retrieval — BM25 + dense vectors with optional HyDE
          expansion.
        </p>
      </div>

      {/* Example queries */}
      <div className="flex max-w-lg flex-col items-center gap-2 sm:flex-row sm:flex-wrap sm:justify-center">
        <span className="text-xs text-slate-600 sm:mr-1">Try asking:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => onExampleClick(ex)}
            className="rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-left text-xs text-slate-400 transition-all duration-150 hover:border-emerald-500/50 hover:bg-emerald-500/5 hover:text-slate-200"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
