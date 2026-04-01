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
                "w-full text-left px-3 py-2.5 rounded-r transition-colors duration-150",
                "flex items-center gap-2 group",
                isActive
                  ? "bg-slate-800 border-l-2 border-emerald-500"
                  : "border-l-2 border-transparent hover:bg-slate-800/50 hover:border-slate-600",
              )}
            >
              <SectionBadge section={sec.section as SectionType} variant="sm" />
              <span
                className={cn(
                  "flex-1 truncate text-sm",
                  isActive ? "text-slate-100" : "text-slate-400 group-hover:text-slate-300",
                )}
              >
                {sec.section_title}
              </span>
              <span
                className={cn(
                  "shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-mono",
                  isActive
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "bg-slate-800 text-slate-500 group-hover:text-slate-400",
                )}
              >
                {sec.num_chunks}
              </span>
            </button>
          );
        })}
      </nav>

      {/* Prev / Next */}
      <div className="mt-3 flex gap-2 border-t border-slate-800 pt-3">
        <button
          onClick={goPrev}
          disabled={currentIndex <= 0}
          className={cn(
            "flex flex-1 items-center justify-center gap-1 rounded px-3 py-1.5 text-xs transition-colors",
            currentIndex > 0
              ? "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-slate-100"
              : "cursor-not-allowed bg-slate-900 text-slate-600",
          )}
        >
          <ChevronUp className="h-3.5 w-3.5" />
          Prev
        </button>
        <button
          onClick={goNext}
          disabled={currentIndex < 0 || currentIndex >= sections.length - 1}
          className={cn(
            "flex flex-1 items-center justify-center gap-1 rounded px-3 py-1.5 text-xs transition-colors",
            currentIndex >= 0 && currentIndex < sections.length - 1
              ? "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-slate-100"
              : "cursor-not-allowed bg-slate-900 text-slate-600",
          )}
        >
          Next
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
