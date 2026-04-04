/**
 * SectionNav — vertical list of sections for the selected filing.
 *
 * Each item shows a SectionBadge, the section title, and chunk count.
 * Prev / Next buttons at the bottom cycle through sections in order.
 */

import { ChevronUp, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { SectionBadge } from "@/components/ui/SectionBadge";
import type { SectionSummary, SectionType } from "@/lib/types";

interface SectionNavProps {
  sections: SectionSummary[];
  selected: SectionType | null;
  onSelect: (section: SectionType) => void;
}

export function SectionNav({ sections, selected, onSelect }: SectionNavProps) {
  const currentIndex = sections.findIndex((s) => s.section === selected);

  const goPrev = () => {
    if (currentIndex > 0) {
      onSelect(sections[currentIndex - 1].section as SectionType);
    }
  };

  const goNext = () => {
    if (currentIndex < sections.length - 1) {
      onSelect(sections[currentIndex + 1].section as SectionType);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Section list */}
      <nav className="flex-1 overflow-y-auto space-y-0.5 pr-1">
        {sections.map((sec) => {
          const isActive = sec.section === selected;
          return (
            <button
              key={sec.section}
              onClick={() => onSelect(sec.section as SectionType)}
              className={cn(
                "group relative flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left transition-all duration-150",
                isActive
                  ? "text-slate-100"
                  : "text-slate-400 hover:text-slate-200",
              )}
              style={
                isActive
                  ? {
                      background:
                        "linear-gradient(135deg, rgba(16,185,129,0.10) 0%, rgba(16,185,129,0.03) 100%)",
                      boxShadow: "inset 0 0 0 1px rgba(16,185,129,0.12)",
                    }
                  : undefined
              }
            >
              {isActive && (
                <div
                  className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full"
                  style={{ background: "linear-gradient(180deg, #10b981, #059669)" }}
                />
              )}
              <SectionBadge section={sec.section as SectionType} variant="sm" />
              <span className="flex-1 truncate text-sm font-medium leading-tight">
                {sec.section_title}
              </span>
              <span
                className={cn(
                  "shrink-0 rounded-full px-1.5 py-0.5 font-mono text-xs",
                  isActive
                    ? "text-emerald-400"
                    : "text-slate-600 group-hover:text-slate-500",
                )}
                style={isActive ? { background: "rgba(16,185,129,0.12)" } : undefined}
              >
                {sec.num_chunks}
              </span>
            </button>
          );
        })}
      </nav>

      {/* Prev / Next */}
      <div
        className="mt-3 flex gap-2 border-t pt-3"
        style={{ borderColor: "rgba(255,255,255,0.05)" }}
      >
        <button
          onClick={goPrev}
          disabled={currentIndex <= 0}
          className={cn(
            "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-all",
            currentIndex > 0
              ? "bg-slate-800/80 text-slate-300 hover:bg-slate-700 hover:text-slate-100"
              : "cursor-not-allowed text-slate-700",
          )}
          style={currentIndex > 0 ? { border: "1px solid rgba(255,255,255,0.06)" } : undefined}
        >
          <ChevronUp className="h-3.5 w-3.5" />
          Prev
        </button>
        <button
          onClick={goNext}
          disabled={currentIndex < 0 || currentIndex >= sections.length - 1}
          className={cn(
            "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-all",
            currentIndex >= 0 && currentIndex < sections.length - 1
              ? "bg-slate-800/80 text-slate-300 hover:bg-slate-700 hover:text-slate-100"
              : "cursor-not-allowed text-slate-700",
          )}
          style={
            currentIndex >= 0 && currentIndex < sections.length - 1
              ? { border: "1px solid rgba(255,255,255,0.06)" }
              : undefined
          }
        >
          Next
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
