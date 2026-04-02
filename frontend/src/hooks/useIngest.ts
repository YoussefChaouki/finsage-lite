/**
 * useIngest hook — orchestrates SEC 10-K ingestion with step simulation.
 *
 * Flow:
 *   1. setStep(0) — Fetching EDGAR
 *   2. POST /api/v1/documents/ingest (timeout 180s, synchronous)
 *   3. Poll GET /api/v1/documents every 2s until doc appears as processed
 *   4. setStep(3) + invalidate React Query cache on success
 *   5. Steps 0→2 are simulated visually every 20s during the wait
 */

import { useState, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { httpClient, listDocuments, ApiError } from "@/lib/api";

interface UseIngestReturn {
  isIngesting: boolean;
  /** Visual step index 0-3. 3 = complete. */
  step: number;
  error: string | null;
  ingest: (ticker: string, year: number) => Promise<void>;
  reset: () => void;
}

const STEP_ADVANCE_MS = 20_000;
const POLL_INTERVAL_MS = 2_000;
const MAX_POLL_ATTEMPTS = 90; // 3 minutes max polling

export function useIngest(): UseIngestReturn {
  const [isIngesting, setIsIngesting] = useState(false);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const queryClient = useQueryClient();
  const stepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cleanup = useCallback(() => {
    if (stepTimerRef.current !== null) {
      clearInterval(stepTimerRef.current);
      stepTimerRef.current = null;
    }
    if (pollTimerRef.current !== null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    cleanup();
    setIsIngesting(false);
    setStep(0);
    setError(null);
  }, [cleanup]);

  const ingest = useCallback(
    async (ticker: string, year: number) => {
      cleanup();
      setIsIngesting(true);
      setStep(0);
      setError(null);

      // Advance visual step every 20s — capped at step 2 (step 3 = confirmed done)
      stepTimerRef.current = setInterval(() => {
        setStep((prev) => Math.min(prev + 1, 2));
      }, STEP_ADVANCE_MS);

      try {
        // Synchronous ingestion — can take 30-120s; override axios timeout
        await httpClient.post(
          "/api/v1/documents/ingest",
          { ticker, fiscal_year: year },
          { timeout: 180_000 },
        );

        // Stop step simulation while polling
        if (stepTimerRef.current !== null) {
          clearInterval(stepTimerRef.current);
          stepTimerRef.current = null;
        }

        // Poll until document appears as processed
        let attempts = 0;
        await new Promise<void>((resolve, reject) => {
          pollTimerRef.current = setInterval(() => {
            attempts++;
            listDocuments()
              .then(({ documents }) => {
                const found = documents.find(
                  (d) =>
                    d.ticker.toUpperCase() === ticker.toUpperCase() &&
                    d.fiscal_year === year &&
                    d.processed,
                );
                if (found) {
                  cleanup();
                  resolve();
                } else if (attempts >= MAX_POLL_ATTEMPTS) {
                  cleanup();
                  reject(new Error("Polling timeout — the document may still be processing"));
                }
              })
              .catch((err: unknown) => {
                cleanup();
                reject(err);
              });
          }, POLL_INTERVAL_MS);
        });

        setStep(3);
        void queryClient.invalidateQueries({ queryKey: ["documents"] });
      } catch (err: unknown) {
        cleanup();
        const msg =
          err instanceof ApiError
            ? err.detail
            : err instanceof Error
              ? err.message
              : "Ingestion failed";
        setError(msg);
      } finally {
        setIsIngesting(false);
      }
    },
    [cleanup, queryClient],
  );

  return { isIngesting, step, error, ingest, reset };
}
