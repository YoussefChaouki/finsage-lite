/**
 * FinSage-Lite — useDocuments hook
 *
 * Fetches GET /api/v1/documents with a 30-second stale time via React Query.
 */

import { useQuery } from "@tanstack/react-query";
import { listDocuments } from "@/lib/api";
import type { DocumentResponse } from "@/lib/types";

interface UseDocumentsReturn {
  documents: DocumentResponse[];
  isLoading: boolean;
  refetch: () => void;
}

export function useDocuments(): UseDocumentsReturn {
  const {
    data,
    isLoading,
    refetch: refetchQuery,
  } = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    staleTime: 30_000,
  });

  return {
    documents: data?.documents ?? [],
    isLoading,
    refetch: () => {
      void refetchQuery();
    },
  };
}
