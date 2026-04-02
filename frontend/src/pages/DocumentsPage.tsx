import { FileText } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FilingCard } from "@/components/documents/FilingCard";
import { IngestForm } from "@/components/documents/IngestForm";
import { IngestProgress } from "@/components/documents/IngestProgress";
import { RebuildIndexButton } from "@/components/documents/RebuildIndexButton";
import { useDocuments } from "@/hooks/useDocuments";
import { useIngest } from "@/hooks/useIngest";

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-700 py-16 text-center">
      {/* Simple document illustration */}
      <svg
        className="mb-4 h-16 w-16 text-slate-700"
        fill="none"
        viewBox="0 0 64 64"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <rect x="12" y="8" width="40" height="48" rx="4" />
        <line x1="20" y1="24" x2="44" y2="24" />
        <line x1="20" y1="32" x2="44" y2="32" />
        <line x1="20" y1="40" x2="36" y2="40" />
      </svg>
      <p className="text-sm font-medium text-slate-300">No filings ingested yet</p>
      <p className="mt-1 text-xs text-slate-500">
        Use the form above to ingest your first 10-K filing
      </p>
    </div>
  );
}

/**
 * Documents page — lists ingested 10-K filings and provides an ingestion form.
 */
export default function DocumentsPage() {
  const { documents, isLoading } = useDocuments();
  const { isIngesting, step, error, ingest } = useIngest();

  const showProgress = isIngesting || step === 3 || error !== null;

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* ── Page header ─────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-100">Documents</h1>
          {!isLoading && (
            <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-medium text-slate-400">
              {documents.length}
            </span>
          )}
        </div>
        <RebuildIndexButton />
      </div>

      {/* ── Ingest form ─────────────────────────────────────── */}
      <Card className="border-slate-800 bg-slate-900">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-slate-200">
            <FileText size={15} className="text-emerald-400" />
            Ingest a Filing
          </CardTitle>
        </CardHeader>
        <CardContent>
          <IngestForm onIngest={ingest} isLoading={isIngesting} />
        </CardContent>
      </Card>

      {/* ── Ingestion progress ──────────────────────────────── */}
      <IngestProgress
        isVisible={showProgress}
        step={step}
        isIngesting={isIngesting}
        error={error}
      />

      {/* ── Document grid ───────────────────────────────────── */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-44 animate-pulse rounded-lg border border-slate-800 bg-slate-900"
            />
          ))}
        </div>
      ) : documents.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {documents.map((doc) => (
            <FilingCard key={doc.id} document={doc} />
          ))}
        </div>
      )}
    </div>
  );
}
