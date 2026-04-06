/**
 * SearchPage — the main search experience.
 *
 * Layout:
 * - Pre-search: hero title centered, search bar centered (max-w-2xl),
 *   empty state fills the full available width below.
 * - Post-search: full-width sticky header (bg covers entire top bar),
 *   results in a readable max-w-4xl column.
 *
 * Bidirectional highlight:
 * - CitationChip hover → highlights matching SourceCard (emerald ring)
 * - SourceCard hover → reflects back to hoveredChunkId state
 *
 * Keyboard shortcuts:
 * - ⌘K / Ctrl+K → focus search input
 * - Esc → clear results and return to initial state
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Info, RotateCcw } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useSearch } from "@/hooks/useSearch";
import { useAppStore } from "@/store/appStore";
import { SearchBar, type SearchBarHandle } from "@/components/search/SearchBar";
import { SearchControls } from "@/components/search/SearchControls";
import { AnswerPanel, type Citation } from "@/components/search/AnswerPanel";
import { SourceCard } from "@/components/search/SourceCard";
import { SearchEmptyState } from "@/components/search/SearchEmptyState";
import { SkeletonCard } from "@/components/ui/SkeletonCard";

export default function SearchPage() {
  const {
    query: lastQuery,
    results,
    answer,
    isLoading,
    error,
    hydeUsed,
    hydeAttempted,
    latencyMs,
    submitSearch,
    clearResults,
  } = useSearch();

  const { selectedCompany, selectedYear, selectedMode, hydeEnabled } =
    useAppStore();

  const [hoveredChunkId, setHoveredChunkId] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const searchBarRef = useRef<SearchBarHandle>(null);

  const citations: Citation[] = results.map((r, i) => ({
    id: i + 1,
    chunk_id: r.chunk_id,
  }));

  // ─── Handlers ──────────────────────────────────────────────────────────────

  const handleSearch = useCallback(
    (q: string): void => {
      setHasSearched(true);
      void submitSearch({
        query: q,
        search_mode: selectedMode,
        use_hyde: hydeEnabled,
        filters: {
          company: selectedCompany,
          fiscal_year: selectedYear,
        },
      });
    },
    [submitSearch, selectedMode, hydeEnabled, selectedCompany, selectedYear],
  );

  const handleExampleClick = useCallback(
    (ex: string): void => {
      searchBarRef.current?.setValue(ex);
      handleSearch(ex);
    },
    [handleSearch],
  );

  const handleClickCitation = useCallback((chunkId: string): void => {
    const el = document.getElementById(`source-${chunkId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    setHoveredChunkId(chunkId);
    setTimeout(() => setHoveredChunkId(null), 2000);
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        searchBarRef.current?.focus();
      } else if (e.key === "Escape" && hasSearched) {
        clearResults();
        setHasSearched(false);
        setHoveredChunkId(null);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [hasSearched, clearResults]);

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex min-h-full flex-col">

      {/* ══════════════════════════════════════════
          PRE-SEARCH STATE — hero + search bar
      ══════════════════════════════════════════ */}
      {!hasSearched && (
        <>
          {/* Hero + search bar — centered section */}
          <div className="flex flex-1 flex-col items-center justify-center px-8 pb-4 pt-16">
            {/* Title */}
            <motion.div
              initial={{ opacity: 0, y: -12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              className="mb-10 text-center"
            >
              <h1 className="font-display text-6xl font-bold tracking-tight text-slate-100 lg:text-7xl">
                FinSage<span className="text-emerald-400">.</span>
              </h1>
              <p className="mt-3 text-base text-slate-500">
                SEC 10-K filing intelligence · hybrid RAG
              </p>
            </motion.div>

            {/* Search bar — focused width */}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="w-full max-w-2xl"
            >
              <SearchBar
                ref={searchBarRef}
                onSubmit={handleSearch}
                isLoading={isLoading}
              />
              <div className="mt-3">
                <SearchControls />
              </div>
            </motion.div>
          </div>

          {/* Empty state — full available width */}
          <div className="px-8 pb-10 lg:px-12">
            <SearchEmptyState onExampleClick={handleExampleClick} />
          </div>
        </>
      )}

      {/* ══════════════════════════════════════════
          POST-SEARCH STATE — sticky header + results
      ══════════════════════════════════════════ */}
      {hasSearched && (
        <>
          {/* Full-width sticky header — bg covers the entire bar */}
          <div
            className="sticky top-0 z-20 w-full border-b border-slate-800/60 bg-slate-950/95 backdrop-blur-sm"
          >
            <div className="mx-auto max-w-4xl px-8 py-4">
              <SearchBar
                ref={searchBarRef}
                onSubmit={handleSearch}
                isLoading={isLoading}
                defaultValue={lastQuery}
              />
              <div className="mt-3">
                <SearchControls />
              </div>
            </div>
          </div>

          {/* Results */}
          <div className="mx-auto w-full max-w-4xl space-y-4 px-8 py-6">
            {/* Error banner */}
            <AnimatePresence>
              {error && (
                <motion.div
                  key="error"
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.2 }}
                  className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400"
                >
                  <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                  <span className="flex-1">{error}</span>
                  {lastQuery && (
                    <button
                      type="button"
                      onClick={() => handleSearch(lastQuery)}
                      className="flex items-center gap-1.5 rounded border border-red-500/30 px-2.5 py-1 text-xs transition-colors hover:bg-red-500/20"
                    >
                      <RotateCcw className="h-3 w-3" />
                      Retry
                    </button>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {/* HyDE offline warning */}
            <AnimatePresence>
              {!isLoading && results.length > 0 && hydeEnabled && hydeAttempted && !hydeUsed && (
                <motion.div
                  key="hyde-warn"
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.2 }}
                  className="flex items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400"
                >
                  <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                  <span>
                    HyDE was requested but Ollama is unavailable. Search ran
                    without query expansion.
                  </span>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Loading skeletons */}
            {isLoading && (
              <div className="space-y-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <SkeletonCard key={i} lines={4} />
                ))}
              </div>
            )}

            {/* AI answer */}
            {!isLoading && answer !== null && (
              <AnswerPanel
                answer={answer}
                citations={citations}
                latencyMs={latencyMs}
                onHoverCitation={setHoveredChunkId}
                onClickCitation={handleClickCitation}
              />
            )}

            {/* No LLM answer info banner */}
            {!isLoading && answer === null && results.length > 0 && (
              <div className="flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-800/40 px-4 py-3 text-sm text-slate-400">
                <Info className="h-4 w-4 flex-shrink-0" />
                <span>
                  Showing retrieved chunks — no AI synthesis available from the LLM.
                </span>
              </div>
            )}

            {/* Source cards */}
            {!isLoading && results.length > 0 && (
              <div>
                <p className="mb-4 text-sm text-slate-500">
                  {results.length} result{results.length !== 1 ? "s" : ""}
                  {latencyMs !== null && <> · {latencyMs.toLocaleString()}ms</>}
                </p>

                <motion.div
                  key={lastQuery ?? "empty"}
                  className="space-y-3"
                  initial="hidden"
                  animate="show"
                  variants={{
                    hidden: {},
                    show: { transition: { staggerChildren: 0.05 } },
                  }}
                >
                  {results.map((result, i) => (
                    <motion.div
                      key={result.chunk_id}
                      variants={{
                        hidden: { opacity: 0, y: 8 },
                        show: {
                          opacity: 1,
                          y: 0,
                          transition: { duration: 0.2, ease: "easeOut" },
                        },
                      }}
                    >
                      <SourceCard
                        result={result}
                        index={i + 1}
                        isHighlighted={hoveredChunkId === result.chunk_id}
                        onMouseEnter={setHoveredChunkId}
                        onMouseLeave={() => setHoveredChunkId(null)}
                      />
                    </motion.div>
                  ))}
                </motion.div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
