/**
 * FinSage-Lite — Axios API client
 *
 * Configured with baseURL from VITE_API_URL env var.
 * Global error interceptor normalises API errors into a typed ApiError.
 */

import axios, { type AxiosError } from "axios";
import type {
  DocumentListResponse,
  DocumentResponse,
  HealthResponse,
  IngestRequest,
  IngestResponse,
  SearchHealthResponse,
  SearchRequest,
  SearchResponse,
} from "@/lib/types";

// ─── Error type ───────────────────────────────────────────────────────────────

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

// ─── Axios instance ───────────────────────────────────────────────────────────

// Use relative URLs so all requests go through the Vite proxy (dev)
// or the same origin (prod). This avoids browser-side hostname resolution
// issues with Docker internal names (e.g. http://api:8000).
const baseURL = "";

export const httpClient = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

/** Normalise Axios errors into ApiError for uniform error handling in the UI. */
httpClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status ?? 0;
    const detail =
      error.response?.data?.detail ??
      error.message ??
      "An unexpected error occurred";
    return Promise.reject(new ApiError(status, detail));
  },
);

// ─── API functions ────────────────────────────────────────────────────────────

/** Check API and Ollama availability. */
export async function getHealth(): Promise<HealthResponse> {
  const { data } = await httpClient.get<HealthResponse>("/health");
  return data;
}

/**
 * Run a search query against the RAG pipeline.
 *
 * @param request - Search parameters (query, top_k, mode, filters…)
 */
export async function search(request: SearchRequest): Promise<SearchResponse> {
  const { data } = await httpClient.post<SearchResponse>(
    "/api/v1/search",
    request,
  );
  return data;
}

/** Get BM25 index stats and Ollama availability. */
export async function getSearchHealth(): Promise<SearchHealthResponse> {
  const { data } = await httpClient.get<SearchHealthResponse>(
    "/api/v1/search/health",
  );
  return data;
}

/** Rebuild the in-memory BM25 index from the database. */
export async function rebuildBm25Index(): Promise<{ chunk_count: number }> {
  const { data } = await httpClient.post<{ chunk_count: number }>(
    "/api/v1/search/rebuild-index",
  );
  return data;
}

/** List all ingested documents. */
export async function listDocuments(): Promise<DocumentListResponse> {
  const { data } = await httpClient.get<DocumentListResponse>(
    "/api/v1/documents",
  );
  return data;
}

/**
 * Fetch a single document by ID (includes section breakdown).
 *
 * @param id - Document UUID
 */
export async function getDocument(id: string): Promise<DocumentResponse> {
  const { data } = await httpClient.get<DocumentResponse>(
    `/api/v1/documents/${id}`,
  );
  return data;
}

/**
 * Trigger ingestion of a SEC 10-K filing.
 *
 * @param request - Ticker symbol and fiscal year
 */
export async function ingestDocument(
  request: IngestRequest,
): Promise<IngestResponse> {
  const { data } = await httpClient.post<IngestResponse>(
    "/api/v1/documents/ingest",
    request,
  );
  return data;
}
