/**
 * BrowsePage — navigate raw filing content by section.
 *
 * Layout:
 *  - FilingSelector across the top
 *  - Below: 256 px sidebar (SectionNav) + flex-1 content (SectionContent)
 */

import { AnimatePresence, motion } from "framer-motion";
import { FileText } from "lucide-react";
import { useBrowse } from "@/hooks/useBrowse";
import { FilingSelector } from "@/components/browse/FilingSelector";
import { SectionNav } from "@/components/browse/SectionNav";
import { SectionContent } from "@/components/browse/SectionContent";
import { SkeletonCard } from "@/components/ui/SkeletonCard";
import type { SectionType } from "@/lib/types";

const sectionVariants = {
  initial: { opacity: 0, x: 12 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -12 },
};

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
      {/* Top bar: filing selector */}
      <div className="shrink-0 border-b border-slate-800 px-6 py-4">
        <div className="max-w-xl">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
            Filing
          </p>
          <FilingSelector
            value={selectedDocumentId}
            onChange={setSelectedDocumentId}
          />
        </div>
      </div>

      {/* No filing selected */}
      {!selectedDocumentId && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
          <FileText className="h-10 w-10 text-slate-700" />
          <p className="text-sm text-slate-500">
            Select a filing above to browse its sections.
          </p>
        </div>
      )}

      {/* Filing selected — main layout */}
      {selectedDocumentId && (
        <div className="flex min-h-0 flex-1 overflow-hidden">
          {/* Sidebar — section nav */}
          <aside className="w-64 shrink-0 overflow-y-auto border-r border-slate-800 px-3 py-4">
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
              <p className="text-xs text-slate-600 px-1">No sections available.</p>
            )}
          </aside>

          {/* Main content area */}
          <main className="relative min-h-0 flex-1 overflow-hidden">
            {!selectedSection ? (
              /* Prompt to pick a section */
              <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
                <p className="text-sm text-slate-500">
                  Select a section from the sidebar.
                </p>
              </div>
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
