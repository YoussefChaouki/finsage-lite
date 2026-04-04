import { motion } from "framer-motion";
import { cn, formatDate, formatNumber, generateAvatarColor } from "@/lib/utils";
import { SectionBadge } from "@/components/ui/SectionBadge";
import type { DocumentResponse, SectionType } from "@/lib/types";

interface FilingCardProps {
  document: DocumentResponse;
  className?: string;
}

function StatusIndicator({ processed }: { processed: boolean }) {
  if (processed) {
    return (
      <span className="flex items-center gap-1.5 text-xs text-emerald-400">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-40" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
        </span>
        ready
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 text-xs text-amber-400">
      <span className="h-2 w-2 rounded-full border-2 border-amber-400 border-t-transparent animate-spin" />
      processing
    </span>
  );
}

/**
 * Card displaying a single SEC 10-K filing.
 * Avatar colour is derived deterministically from the ticker.
 */
export function FilingCard({ document, className }: FilingCardProps) {
  const avatarBg = generateAvatarColor(document.ticker);
  const initials = document.ticker.slice(0, 2).toUpperCase();
  const availableSections = document.sections.map((s) => s.section as SectionType);

  return (
    <motion.div
      whileHover={{ scale: 1.01 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={cn(
        "group flex flex-col rounded-xl border border-slate-800 bg-slate-900 p-5 transition-colors",
        "hover:border-slate-700 hover:bg-slate-800/50",
        className,
      )}
    >
      {/* ── Header ───────────────────────────────────────────── */}
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-white"
          style={{ backgroundColor: avatarBg }}
        >
          {initials}
        </div>

        <div className="min-w-0 flex-1">
          <p className="truncate text-base font-semibold text-slate-100">
            {document.company_name}
          </p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <span className="inline-flex items-center rounded border border-slate-700 bg-slate-800 px-1.5 py-0 font-mono text-xs font-medium text-slate-300">
              {document.ticker}
            </span>
            <span className="inline-flex items-center rounded border border-slate-700 bg-slate-800 px-1.5 py-0 font-mono text-xs font-medium text-slate-300">
              FY{document.fiscal_year}
            </span>
            <span className="inline-flex items-center rounded border border-slate-700 bg-slate-800 px-1.5 py-0 text-xs text-slate-400">
              {document.filing_type}
            </span>
          </div>
        </div>
      </div>

      {/* ── Body ─────────────────────────────────────────────── */}
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-400">
        <div>
          <span className="text-slate-500">Chunks</span>
          <p className="mt-0.5 font-mono text-slate-200">
            {formatNumber(document.num_chunks)}
          </p>
        </div>
        <div>
          <span className="text-slate-500">Filed</span>
          <p className="mt-0.5 text-slate-200">{formatDate(document.filing_date)}</p>
        </div>
      </div>

      {/* ── Sections ─────────────────────────────────────────── */}
      {availableSections.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {availableSections.map((section) => (
            <SectionBadge key={section} section={section} variant="sm" />
          ))}
        </div>
      )}

      {/* ── Footer ───────────────────────────────────────────── */}
      <div className="mt-3 flex items-center justify-between border-t border-slate-800 pt-3">
        <span className="truncate font-mono text-xs text-slate-500">
          {document.accession_no}
        </span>
        <StatusIndicator processed={document.processed} />
      </div>
    </motion.div>
  );
}
