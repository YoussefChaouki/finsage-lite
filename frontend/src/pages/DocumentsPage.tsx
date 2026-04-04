import { FileText, Building2, CheckCircle2, Layers } from "lucide-react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FilingCard } from "@/components/documents/FilingCard";
import { IngestForm } from "@/components/documents/IngestForm";
import { IngestProgress } from "@/components/documents/IngestProgress";
import { RebuildIndexButton } from "@/components/documents/RebuildIndexButton";
import { useDocuments } from "@/hooks/useDocuments";
import { useIngest } from "@/hooks/useIngest";
import type { DocumentResponse } from "@/lib/types";

const gridVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05 } },
};

const cardItemVariants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.2, ease: "easeOut" as const } },
};

interface StatTileProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  accent?: string;
}

function StatTile({ icon, label, value, accent = "text-slate-300" }: StatTileProps) {
  return (
    <div
      className="flex items-center gap-3 rounded-xl border px-4 py-3.5"
      style={{
        borderColor: "rgba(255,255,255,0.06)",
        background: "rgba(255,255,255,0.02)",
      }}
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800/80">
        {icon}
      </div>
      <div>
        <p className={`text-base font-bold leading-none tabular-nums ${accent}`}>{value}</p>
        <p className="mt-1 text-[11px] text-slate-600">{label}</p>
      </div>
    </div>
  );
}

function StatsStrip({ documents }: { documents: DocumentResponse[] }) {
  const totalChunks = documents.reduce((s, d) => s + d.num_chunks, 0);
  const uniqueCompanies = new Set(documents.map((d) => d.ticker)).size;
  const readyCount = documents.filter((d) => d.processed).length;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatTile
        icon={<FileText className="h-4 w-4 text-slate-500" />}
        label="Total filings"
        value={documents.length}
        accent="text-slate-200"
      />
      <StatTile
        icon={<Layers className="h-4 w-4 text-emerald-500/70" />}
        label="Total chunks"
        value={totalChunks.toLocaleString()}
        accent="text-emerald-400"
      />
      <StatTile
        icon={<Building2 className="h-4 w-4 text-sky-500/70" />}
        label="Companies"
        value={uniqueCompanies}
        accent="text-sky-400"
      />
      <StatTile
        icon={<CheckCircle2 className="h-4 w-4 text-violet-400/70" />}
        label="Ready"
        value={`${readyCount} / ${documents.length}`}
        accent="text-violet-400"
      />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 py-20 text-center">
      {/* Simple document illustration */}
      <svg
        className="mb-5 h-20 w-20 text-slate-700"
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
      <p className="text-base font-semibold text-slate-300">No filings ingested yet</p>
      <p className="mt-1.5 text-sm text-slate-500">
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
    <div className="flex flex-col gap-8 px-8 py-8">
      {/* ── Page header ─────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-slate-100">
              Documents
            </h1>
            <p className="mt-0.5 text-sm text-slate-500">
              Manage your SEC 10-K filings
            </p>
          </div>
          {!isLoading && (
            <span className="rounded-full bg-slate-800 px-3 py-1 text-sm font-medium text-slate-400 border border-slate-700">
              {documents.length} filing{documents.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <RebuildIndexButton />
      </div>

      {/* ── Stats strip ─────────────────────────────────────── */}
      {!isLoading && documents.length > 0 && (
        <StatsStrip documents={documents} />
      )}

      {/* ── Ingest form ─────────────────────────────────────── */}
      <Card className="border-slate-800 bg-slate-900">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2.5 text-base font-semibold text-slate-200">
            <FileText size={17} className="text-emerald-400" />
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
        <motion.div
          className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
          variants={gridVariants}
          initial="hidden"
          animate="show"
        >
          {documents.map((doc) => (
            <motion.div key={doc.id} variants={cardItemVariants}>
              <FilingCard document={doc} />
            </motion.div>
          ))}
        </motion.div>
      )}
    </div>
  );
}
