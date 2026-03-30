/**
 * FinSage-Lite — useSearch hook
 *
 * Manages search state and calls POST /api/v1/search.
 */

import { useState, useCallback } from "react";
import { search as searchApi, ApiError } from "@/lib/api";
import type { SearchMode, SearchResult, SearchFilters } from "@/lib/types";

export interface SearchParams {
  query: string;
  top_k?: number;
  search_mode?: SearchMode;
  use_hyde?: boolean;
  filters?: SearchFilters;
}

interface UseSearchReturn {
  query: string;
  results: SearchResult[];
  answer: string | null;
  isLoading: boolean;
  error: string | null;
  hydeUsed: boolean;
  latencyMs: number | null;
  submitSearch: (params: SearchParams) => Promise<void>;
  clearResults: () => void;
}

export function useSearch(): UseSearchReturn {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [answer, setAnswer] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hydeUsed, setHydeUsed] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);

  const submitSearch = useCallback(
    async (params: SearchParams): Promise<void> => {
      setIsLoading(true);
      setError(null);
      setQuery(params.query);

      try {
        const response = await searchApi(params);
        setResults(response.results);
        setAnswer(response.answer);
        setHydeUsed(response.hyde_used);
        setLatencyMs(response.latency_ms);
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 0) {
            setError("Cannot reach the API — is the backend running?");
          } else if (err.status >= 500) {
            setError("Server error. Please try again later.");
          } else {
            setError(err.detail);
          }
        } else {
          setError("An unexpected error occurred.");
        }
        setResults([]);
        setAnswer(null);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const clearResults = useCallback((): void => {
    setQuery("");
    setResults([]);
    setAnswer(null);
    setError(null);
    setHydeUsed(false);
    setLatencyMs(null);
  }, []);

  return {
    query,
    results,
    answer,
    isLoading,
    error,
    hydeUsed,
    latencyMs,
    submitSearch,
    clearResults,
  };
}
