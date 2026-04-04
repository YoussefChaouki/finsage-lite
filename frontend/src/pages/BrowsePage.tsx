/**
 * BrowsePage — navigate raw filing content by section.
 *
 * Layout:
 *  - Page header with title + inline FilingSelector
 *  - No filing selected → rich empty state with section preview
 *  - Filing selected, no section → interactive section picker grid
 *  - Filing + section → SectionNav (left) + SectionContent (right)
 */

import { AnimatePresence, motion } from "framer-motion";
import { BookOpen } from "lucide-react";
import { useBrowse } from "@/hooks/useBrowse";
import { FilingSelector } from "@/components/browse/FilingSelector";
import { SectionNav } from "@/components/browse/SectionNav";
import { SectionContent } from "@/components/browse/SectionContent";
import { SectionBadge } from "@/components/ui/SectionBadge";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import { SECTION_LABELS } from "@/lib/constants";
import type { SectionSummary, SectionType } from "@/lib/types";

const sectionVariants = {
  initial: { opacity: 0, x: 12 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -12 },
};

// ─── Section colour map for the picker grid ───────────────────────────────────

const SECTION_ACCENT: Record<SectionType, string> = {
  ITEM_1: "#0ea5e9",
  ITEM_1A: "#ef4444",
  ITEM_7: "#10b981",
  ITEM_7A: "#f97316",
  ITEM_8: "#8b5cf6",
  OTHER: "#475569",
};

// ─── Sub-components ───────────────────────────────────────────────────────────

/** Rich placeholder when no filing is selected. */
function NoFilingState() {
  const previewSections: { label: SectionType; color: string }[] = [
    { label: "ITEM_1", color: "#0ea5e9" },
    { label: "ITEM_1A", color: "#ef4444" },
    { label: "ITEM_7", color: "#10b981" },
    { label: "ITEM_7A", color: "#f97316" },
    { label: "ITEM_8", color: "#8b5cf6" },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-1 flex-col items-center justify-center gap-8 p-8"
    >
      {/* Glowing icon */}
      <div className="relative">
        <div
          className="pointer-events-none absolute -inset-8 rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(16,185,129,0.07) 0%, transparent 70%)",
            filter: "blur(8px)",
          }}
        />
        <div
          className="relative flex h-20 w-20 items-center justify-center rounded-2xl"
          style={{
            background:
              "linear-gradient(135deg, rgba(16,185,129,0.10) 0%, rgba(16,185,129,0.03) 100%)",
            border: "1px solid rgba(16,185,129,0.18)",
            boxShadow: "0 0 32px rgba(16,185,129,0.08)",
          }}
        >
          <BookOpen className="h-9 w-9 text-emerald-500/60" strokeWidth={1.5} />
        </div>
      </div>

      {/* Copy */}
      <div className="max-w-sm text-center">
        <h3 className="font-display text-xl font-semibold text-slate-200">
          Explore Sections
        </h3>
        <p className="mt-2.5 text-sm leading-relaxed text-slate-500">
          Select an ingested 10-K filing above to navigate its sections —
          Business, Risk Factors, MD&A, Financial Statements, and more.
        </p>
      </div>

      {/* Section preview chips */}
      <div className="flex flex-wrap justify-center gap-2">
        {previewSections.map(({ label, color }) => (
          <div
            key={label}
            className="flex items-center gap-2 rounded-full px-3 py-1.5 opacity-40"
            style={{
              border: `1px solid ${color}28`,
              background: `${color}0a`,
            }}
          >
            <span
              className="font-mono text-[11px] font-bold"
              style={{ color }}
            >
              {label.replace("_", " ")}
            </span>
            <span className="text-xs text-slate-500">
              {SECTION_LABELS[label]}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

/** Grid of all sections as clickable cards — shown when no section is selected yet. */
function SectionPickerGrid({
  sections,
  onSelect,
}: {
  sections: SectionSummary[];
  onSelect: (s: SectionType) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="h-full overflow-y-auto px-8 py-8"
    >
      <div className="mb-6">
        <h3 className="font-display text-lg font-semibold text-slate-200">
          Choose a section
        </h3>
        <p className="mt-1 text-sm text-slate-500">
          Click any card to start reading
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        {sections.map((sec, i) => {
          const accent = SECTION_ACCENT[sec.section as SectionType] ?? "#475569";
          return (
            <motion.button
              key={sec.section}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, delay: i * 0.06, ease: "easeOut" }}
              onClick={() => onSelect(sec.section as SectionType)}
              className="group rounded-xl border border-slate-800 bg-slate-900/60 p-5 text-left transition-all duration-150 hover:border-slate-700 hover:bg-slate-800/70"
              style={{
                ["--accent" as string]: accent,
              }}
            >
              {/* Score bar accent strip */}
              <div
                className="mb-3 h-0.5 w-8 rounded-full opacity-60 transition-all duration-200 group-hover:w-12 group-hover:opacity-100"
                style={{ background: accent }}
              />

              <div className="mb-3 flex items-center justify-between">
                <SectionBadge section={sec.section as SectionType} variant="sm" />
                <span className="font-mono text-xs text-slate-600">
                  {sec.num_chunks} chunks
                </span>
              </div>

              <p className="text-sm font-semibold leading-tight text-slate-300 transition-colors group-hover:text-slate-100">
                {sec.section_title}
              </p>
            </motion.button>
          );
        })}
      </div>
    </motion.div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function BrowsePage() {
  const {
    selectedDocumentId,
    setSelectedDocumentId,
    selectedSection,
    setSelectedSection,
    document,
    chunks,
    isLoadingDocument,
    isLoadingChunks,
    chunksError,
  } = useBrowse();

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* ── Page header ─────────────────────────────────────── */}
      <div
        className="shrink-0 border-b px-8 py-5"
        style={{ borderColor: "rgba(255,255,255,0.05)" }}
      >
        <div className="flex items-center justify-between gap-6">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight text-slate-100">
              Browse
            </h1>
            <p className="mt-0.5 text-sm text-slate-500">
              {selectedDocumentId && document
                ? `${document.company_name} · FY${document.fiscal_year} · ${document.sections.length} section${document.sections.length !== 1 ? "s" : ""}`
                : "Navigate SEC 10-K filing sections"}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-slate-600 sm:block">Filing</span>
            <div className="w-72">
              <FilingSelector
                value={selectedDocumentId}
                onChange={setSelectedDocumentId}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── No filing selected ──────────────────────────────── */}
      {!selectedDocumentId && <NoFilingState />}

      {/* ── Filing selected ─────────────────────────────────── */}
      {selectedDocumentId && (
        <div className="flex min-h-0 flex-1 overflow-hidden">
          {/* Left: section nav */}
          <aside
            className="w-64 shrink-0 overflow-y-auto border-r px-3 py-4"
            style={{ borderColor: "rgba(255,255,255,0.05)" }}
          >
            {isLoadingDocument ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <SkeletonCard key={i} lines={1} className="py-2" />
                ))}
              </div>
            ) : document && document.sections.length > 0 ? (
              <SectionNav
                sections={document.sections}
                selected={selectedSection}
                onSelect={(s: SectionType) => setSelectedSection(s)}
              />
            ) : (
              <p className="px-1 text-xs text-slate-600">No sections available.</p>
            )}
          </aside>

          {/* Right: content area */}
          <main className="relative min-h-0 flex-1 overflow-hidden">
            {!selectedSection ? (
              /* Show section picker grid */
              document && document.sections.length > 0 ? (
                <SectionPickerGrid
                  sections={document.sections}
                  onSelect={(s) => setSelectedSection(s)}
                />
              ) : (
                <div className="flex h-full items-center justify-center">
                  <p className="text-sm text-slate-500">Select a section from the sidebar.</p>
                </div>
              )
            ) : (
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={selectedSection}
                  variants={sectionVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                  transition={{ duration: 0.18, ease: "easeInOut" }}
                  className="absolute inset-0"
                >
                  <SectionContent
                    chunks={chunks}
                    error={chunksError}
                    sectionTitle={
                      document?.sections.find((s) => s.section === selectedSection)
                        ?.section_title ?? selectedSection
                    }
                    isLoading={isLoadingChunks}
                  />
                </motion.div>
              </AnimatePresence>
            )}
          </main>
        </div>
      )}
    </div>
  );
}
