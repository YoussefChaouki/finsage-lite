/**
 * SectionContent — renders all chunks of a selected filing section.
 *
 * TEXT chunks are displayed as prose; TABLE chunks show a formatted table
 * via TableChunkView. A loading skeleton is shown while fetching.
 */

import { useEffect, useRef } from "react";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { TableChunkView } from "@/components/search/TableChunkView";
import type { SearchResult } from "@/lib/types";

interface SectionContentProps {
  chunks: SearchResult[];
  sectionTitle: string;
  isLoading: boolean;
  error?: Error | null;
}

export function SectionContent({ chunks, sectionTitle, isLoading, error }: SectionContentProps) {
  const topRef = useRef<HTMLDivElement>(null);

  // Scroll to top on every section change (when chunks update)
  useEffect(() => {
    topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [sectionTitle]);

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center p-6">
        <p className="text-sm text-red-400">Failed to load chunks.</p>
        <p className="text-xs text-slate-600">{error.message}</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} lines={5} />
        ))}
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div ref={topRef} />

      {/* Header */}
      <div
        className="sticky top-0 z-10 flex items-center justify-between border-b px-6 py-4 backdrop-blur-md"
        style={{
          background: "rgba(6,11,22,0.92)",
          borderColor: "rgba(255,255,255,0.05)",
        }}
      >
        <h2 className="font-display text-base font-semibold text-slate-100">{sectionTitle}</h2>
        <span
          className="rounded-full px-3 py-1 font-mono text-xs text-slate-400"
          style={{
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.07)",
          }}
        >
          {chunks.length} chunks
        </span>
      </div>

      {/* Chunks */}
      <div className="space-y-0 px-8 py-6">
        {chunks.map((chunk, idx) => {
          const tableTitle = typeof chunk.metadata.table_title === "string"
            ? chunk.metadata.table_title
            : undefined;
          const isTable = tableTitle !== undefined;

          return (
            <div key={chunk.chunk_id}>
              {idx > 0 && (
                <div
                  className="my-5 h-px"
                  style={{ background: "rgba(255,255,255,0.04)" }}
                />
              )}
              <div className="space-y-2">
                {isTable ? (
                  <>
                    <p className="text-sm font-medium text-slate-400">
                      📊 {tableTitle}
                    </p>
                    <TableChunkView content={chunk.content} tableTitle={tableTitle} />
                  </>
                ) : (
                  <p className="text-[0.9375rem] leading-[1.8] text-slate-300 whitespace-pre-wrap">
                    {chunk.content}
                  </p>
                )}
              </div>
            </div>
          );
        })}

        {chunks.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center gap-2">
            <p className="text-base text-slate-500">No chunks found for this section.</p>
            <p className="text-sm text-slate-700">The section may be empty or not yet processed.</p>
          </div>
        )}
      </div>
    </div>
  );
}
