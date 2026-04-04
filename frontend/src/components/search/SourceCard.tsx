/**
 * SourceCard — displays a single search result chunk.
 *
 * Features:
 * - Section badge, table indicator, section title, relevance ScoreBar
 * - Content expandable with Framer Motion height animation
 * - Emerald ring highlight when bidirectionally linked to a CitationChip
 * - Metadata footer: company, fiscal year, approx page, chunk ID prefix
 */

import { useState } from "react";
import { ChevronDown, ChevronUp, Table2 } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { SectionBadge } from "@/components/ui/SectionBadge";
import { ScoreBar } from "@/components/ui/ScoreBar";
import { TableChunkView } from "./TableChunkView";
import type { SearchResult } from "@/lib/types";

interface SourceCardProps {
  result: SearchResult;
  index: number;
  isHighlighted: boolean;
  onMouseEnter: (chunkId: string) => void;
  onMouseLeave: () => void;
}

export function SourceCard({
  result,
  index,
  isHighlighted,
  onMouseEnter,
  onMouseLeave,
}: SourceCardProps) {
  const [expanded, setExpanded] = useState(false);

  const tableTitle =
    typeof result.metadata.table_title === "string"
      ? result.metadata.table_title
      : undefined;
  const isTable = tableTitle !== undefined;

  return (
    <div
      id={`source-${result.chunk_id}`}
      className={cn(
        "rounded-xl border bg-slate-900/80 transition-all duration-200",
        isHighlighted
          ? "border-emerald-500/50 ring-2 ring-emerald-500 ring-offset-2 ring-offset-slate-950"
          : "border-slate-800 hover:border-slate-700",
      )}
      onMouseEnter={() => onMouseEnter(result.chunk_id)}
      onMouseLeave={onMouseLeave}
    >
      {/* Header */}
      <div className="flex items-start gap-3 p-4 pb-3">
        <span className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-800 font-mono text-xs font-bold text-slate-400">
          {index}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <SectionBadge section={result.section} variant="sm" />
            {isTable && (
              <span className="inline-flex items-center gap-1 rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 font-mono text-xs text-amber-400">
                <Table2 className="h-3 w-3" />
                TABLE
              </span>
            )}
            <span className="truncate text-xs font-medium text-slate-300">
              {result.section_title}
            </span>
          </div>
          <div className="mt-2">
            <ScoreBar score={result.score} />
          </div>
        </div>
      </div>

      {/* Content with animated expand/collapse */}
      <div className="px-4 pb-3">
        <motion.div
          initial={false}
          animate={{ height: expanded ? "auto" : "5rem" }}
          transition={{ duration: 0.25, ease: "easeInOut" }}
          className="overflow-hidden"
        >
          {isTable ? (
            <TableChunkView content={result.content} tableTitle={tableTitle} />
          ) : (
            <p className="text-sm leading-relaxed text-slate-300">
              {result.content}
            </p>
          )}
        </motion.div>

        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 flex items-center gap-1 text-xs text-slate-500 transition-colors hover:text-slate-300"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              Show more
            </>
          )}
        </button>
      </div>

      {/* Metadata footer */}
      <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 px-4 py-2.5">
        {typeof result.metadata.company === "string" && (
          <span className="text-xs text-slate-500">
            {result.metadata.company}
          </span>
        )}
        {typeof result.metadata.fiscal_year === "number" && (
          <span className="text-xs text-slate-500">
            FY{result.metadata.fiscal_year}
          </span>
        )}
        {typeof result.metadata.page_approx === "number" && (
          <span className="text-xs text-slate-500">
            ~p.{result.metadata.page_approx}
          </span>
        )}
        <span className="ml-auto max-w-[8rem] truncate font-mono text-xs text-slate-600">
          {result.chunk_id.slice(0, 8)}…
        </span>
      </div>
    </div>
  );
}
