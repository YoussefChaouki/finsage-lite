/**
 * FinSage-Lite — useBrowse hook
 *
 * Manages state for the Browse Filing page:
 * selected document → fetch sections, selected section → fetch chunks.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getDocument, search as searchApi } from "@/lib/api";
import type { DocumentResponse, SearchResult, SectionType } from "@/lib/types";

export interface UseBrowseReturn {
  selectedDocumentId: string | null;
  setSelectedDocumentId: (id: string | null) => void;
  selectedSection: SectionType | null;
  setSelectedSection: (section: SectionType | null) => void;
  document: DocumentResponse | null;
  chunks: SearchResult[];
  isLoadingDocument: boolean;
  isLoadingChunks: boolean;
  chunksError: Error | null;
}

export function useBrowse(): UseBrowseReturn {
  const [selectedDocumentId, setSelectedDocumentIdRaw] = useState<string | null>(null);
  const [selectedSection, setSelectedSection] = useState<SectionType | null>(null);

  const { data: document, isLoading: isLoadingDocument } = useQuery({
    queryKey: ["document", selectedDocumentId],
    queryFn: () => getDocument(selectedDocumentId!),
    enabled: selectedDocumentId !== null,
    staleTime: 60_000,
  });

  const { data: searchResponse, isLoading: isLoadingChunks, error: chunksError } = useQuery({
    queryKey: ["browse-chunks", selectedDocumentId, selectedSection],
    queryFn: () =>
      searchApi({
        query: ".",
        search_mode: "dense",
        top_k: 50,
        filters: {
          document_id: selectedDocumentId!,
          sections: [selectedSection!],
        },
      }),
    enabled: selectedDocumentId !== null && selectedSection !== null,
    staleTime: 60_000,
    retry: 1,
  });

  const chunks = (searchResponse?.results ?? []).slice().sort((a, b) => {
    const ia = typeof a.metadata.chunk_index === "number" ? a.metadata.chunk_index : 0;
    const ib = typeof b.metadata.chunk_index === "number" ? b.metadata.chunk_index : 0;
    return ia - ib;
  });

  const setSelectedDocumentId = (id: string | null) => {
    setSelectedDocumentIdRaw(id);
    setSelectedSection(null);
  };

  return {
    selectedDocumentId,
    setSelectedDocumentId,
    selectedSection,
    setSelectedSection,
    document: document ?? null,
    chunks,
    isLoadingDocument,
    isLoadingChunks,
    chunksError: (chunksError as Error | null) ?? null,
  };
}
