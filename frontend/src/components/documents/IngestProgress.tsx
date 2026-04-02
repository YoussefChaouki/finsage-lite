import { CheckCircle, Loader2, Circle, Globe, FileText, Cpu, Database } from "lucide-react";
import { cn } from "@/lib/utils";

interface Step {
  label: string;
  Icon: React.ElementType;
}

const STEPS: Step[] = [
  { label: "Fetching EDGAR", Icon: Globe },
  { label: "Parsing HTML", Icon: FileText },
  { label: "Chunking & Embedding", Icon: Cpu },
  { label: "Storing", Icon: Database },
];

interface IngestProgressProps {
  isVisible: boolean;
  /** Current step index 0-3. 3 = complete. */
  step: number;
  isIngesting: boolean;
  error: string | null;
}

/**
 * Animated 4-step progress stepper for the ingestion pipeline.
 * Steps: Fetching EDGAR → Parsing HTML → Chunking & Embedding → Storing.
 */
export function IngestProgress({
  isVisible,
  step,
  isIngesting,
  error,
}: IngestProgressProps) {
  if (!isVisible) return null;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-medium text-slate-200">Ingestion Progress</p>
        {isIngesting && (
          <p className="text-xs text-slate-500">~60s for a typical 10-K</p>
        )}
      </div>

      <ol className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-0">
        {STEPS.map((s, i) => {
          const isDone = step > i || (!isIngesting && !error && step === i);
          const isActive = isIngesting && step === i;
          const isPending = step < i;

          return (
            <li key={s.label} className="flex items-center gap-2 sm:flex-1">
              {/* Step circle */}
              <div className="shrink-0">
                {isDone && !isActive ? (
                  <CheckCircle size={18} className="text-emerald-500" />
                ) : isActive ? (
                  <Loader2 size={18} className="animate-spin text-emerald-400" />
                ) : error && step === i ? (
                  <Circle size={18} className="text-red-400" />
                ) : (
                  <Circle size={18} className={cn(isPending ? "text-slate-700" : "text-slate-500")} />
                )}
              </div>

              {/* Step label */}
              <span
                className={cn(
                  "flex items-center gap-1 text-xs",
                  isDone && !isActive ? "text-emerald-400" : "",
                  isActive ? "font-medium text-emerald-300" : "",
                  isPending ? "text-slate-600" : "",
                  !isDone && !isActive && !isPending ? "text-slate-400" : "",
                )}
              >
                <s.Icon size={12} className="shrink-0" />
                {s.label}
              </span>

              {/* Connector line (hidden on last step) */}
              {i < STEPS.length - 1 && (
                <div
                  className={cn(
                    "hidden h-px flex-1 sm:block",
                    step > i ? "bg-emerald-800" : "bg-slate-800",
                  )}
                />
              )}
            </li>
          );
        })}
      </ol>

      {/* Error message */}
      {error && (
        <p className="mt-3 rounded border border-red-900 bg-red-950/50 px-3 py-2 text-xs text-red-400">
          {error}
        </p>
      )}

      {/* Success message */}
      {!isIngesting && !error && step === 3 && (
        <p className="mt-3 rounded border border-emerald-900 bg-emerald-950/50 px-3 py-2 text-xs text-emerald-400">
          Filing ingested successfully.
        </p>
      )}
    </div>
  );
}
