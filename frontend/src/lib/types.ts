/**
 * FinSage-Lite — TypeScript types
 *
 * Strict mirror of the Pydantic schemas in src/schemas/.
 * No `any` — unknown metadata fields use `Record<string, unknown>`.
 */

// ─── Enums ────────────────────────────────────────────────────────────────────

/** SEC 10-K section identifiers (mirrors SectionType in src/models/chunk.py). */
export type SectionType =
  | "ITEM_1"
  | "ITEM_1A"
  | "ITEM_7"
  | "ITEM_7A"
  | "ITEM_8"
  | "OTHER";

/** Retrieval strategy for the search endpoint. */
export type SearchMode = "dense" | "sparse" | "hybrid";

// ─── Search ───────────────────────────────────────────────────────────────────

/** Pre-filtering criteria applied before retrieval (mirrors SearchFilters). */
export interface SearchFilters {
  document_id?: string | null;
  sections?: SectionType[] | null;
  fiscal_year?: number | null;
  company?: string | null;
}

/** Request body for POST /api/v1/search (mirrors SearchRequest). */
export interface SearchRequest {
  query: string;
  top_k?: number;
  search_mode?: SearchMode;
  use_hyde?: boolean;
  generate?: boolean;
  filters?: SearchFilters;
}

/** A single hybrid (RRF-fused) result (mirrors SearchResult). */
export interface SearchResult {
  chunk_id: string;
  document_id: string;
  content: string;
  section: SectionType;
  section_title: string;
  score: number;
  dense_score: number | null;
  sparse_score: number | null;
  metadata: Record<string, unknown>;
}

/** Response body for POST /api/v1/search (mirrors SearchResponse). */
export interface SearchResponse {
  answer: string | null;
  results: SearchResult[];
  total: number;
  query: string;
  search_mode: string;
  hyde_used: boolean;
  hyde_attempted: boolean;
  latency_ms: number;
}

/** Response body for GET /api/v1/search/health (mirrors SearchHealthResponse). */
export interface SearchHealthResponse {
  bm25_index_size: number;
  bm25_is_built: boolean;
  hyde_available: boolean;
  ollama_model: string;
}

// ─── Documents ────────────────────────────────────────────────────────────────

/** Request body for POST /api/v1/documents/ingest (mirrors IngestRequest). */
export interface IngestRequest {
  ticker: string;
  fiscal_year: number;
}

/** Response after ingestion completes (mirrors IngestResponse). */
export interface IngestResponse {
  document_id: string;
  status: string;
  message: string;
}

/** Summary of a section within a document (mirrors SectionSummary). */
export interface SectionSummary {
  section: string;
  section_title: string;
  num_chunks: number;
}

/** Full document representation (mirrors DocumentResponse). */
export interface DocumentResponse {
  id: string;
  company_name: string;
  ticker: string;
  cik: string;
  fiscal_year: number;
  filing_type: string;
  filing_date: string;    // ISO date string
  accession_no: string;
  source_url: string;
  processed: boolean;
  created_at: string;     // ISO datetime string
  num_chunks: number;
  sections: SectionSummary[];
}

/** Response for listing documents (mirrors DocumentListResponse). */
export interface DocumentListResponse {
  documents: DocumentResponse[];
  total: number;
}

// ─── Health ───────────────────────────────────────────────────────────────────

/** Response from GET /health (mirrors HealthResponse). */
export interface HealthResponse {
  status: string;
  ollama_available: boolean;
  database_available: boolean;
}
