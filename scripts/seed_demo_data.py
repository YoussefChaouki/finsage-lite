"""
Seed Demo Data

Ingests three SEC 10-K filings (AAPL, MSFT, GOOGL FY2024) into a running
FinSage-Lite API, then rebuilds the BM25 index and prints a summary.

Usage:
    python scripts/seed_demo_data.py [--api-url http://localhost:8000]

Exits with code 0 on success, 1 on any failure.
"""

import argparse
import sys
import time

import httpx

FILINGS = [
    {"ticker": "AAPL", "fiscal_year": 2024},
    {"ticker": "MSFT", "fiscal_year": 2024},
    {"ticker": "GOOGL", "fiscal_year": 2024},
]

INGEST_TIMEOUT = 180.0  # SEC EDGAR download + processing can take a while
POLL_INTERVAL = 3.0
POLL_TIMEOUT = 30.0


def wait_for_api(base_url: str, timeout: float = 30.0) -> None:
    """Block until /health returns 200 or timeout expires."""
    deadline = time.monotonic() + timeout
    print(f"Waiting for API at {base_url} …", flush=True)
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=2.0)
            if r.status_code == 200:
                print("API ready.\n", flush=True)
                return
        except httpx.RequestError:
            pass
        time.sleep(1.0)
    print("ERROR: API unreachable — is Docker running?", file=sys.stderr)
    sys.exit(1)


def ingest_filing(client: httpx.Client, base_url: str, ticker: str, fiscal_year: int) -> dict:  # type: ignore[type-arg]
    """POST /api/v1/documents/ingest and return the response JSON."""
    print(f"  Ingesting {ticker} FY{fiscal_year} …", end=" ", flush=True)
    t0 = time.monotonic()
    r = client.post(
        f"{base_url}/api/v1/documents/ingest",
        json={"ticker": ticker, "fiscal_year": fiscal_year},
        timeout=INGEST_TIMEOUT,
    )
    elapsed = time.monotonic() - t0

    if r.status_code not in (200, 201):
        print(f"FAILED (HTTP {r.status_code}): {r.text}", flush=True)
        sys.exit(1)

    data: dict = r.json()  # type: ignore[type-arg]
    status = data.get("status", "?")
    print(f"{status} ({elapsed:.1f}s)", flush=True)
    return data


def rebuild_index(client: httpx.Client, base_url: str) -> int:
    """POST /api/v1/search/rebuild-index and return chunk_count."""
    print("Rebuilding BM25 index …", end=" ", flush=True)
    r = client.post(f"{base_url}/api/v1/search/rebuild-index", timeout=30.0)
    if r.status_code != 200:
        print(f"FAILED (HTTP {r.status_code})", flush=True)
        sys.exit(1)
    chunk_count: int = r.json().get("chunk_count", 0)
    print(f"done ({chunk_count} chunks indexed)", flush=True)
    return chunk_count


def get_documents(client: httpx.Client, base_url: str) -> list:  # type: ignore[type-arg]
    """GET /api/v1/documents and return the document list."""
    r = client.get(f"{base_url}/api/v1/documents", timeout=10.0)
    if r.status_code != 200:
        return []
    return r.json().get("documents", [])  # type: ignore[no-any-return]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed FinSage-Lite demo data")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL of the FastAPI backend (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    base_url: str = args.api_url.rstrip("/")

    wait_for_api(base_url)

    overall_start = time.monotonic()

    with httpx.Client() as client:
        print("── Ingesting filings ──────────────────────────────────")
        ingested_ids = []
        for filing in FILINGS:
            result = ingest_filing(client, base_url, filing["ticker"], filing["fiscal_year"])
            if doc_id := result.get("document_id"):
                ingested_ids.append(doc_id)

        print()
        chunk_count = rebuild_index(client, base_url)

        print()
        print("── Summary ────────────────────────────────────────────")
        docs = get_documents(client, base_url)
        total_chunks = sum(d.get("num_chunks", 0) for d in docs)
        companies = {d.get("ticker") for d in docs}
        elapsed_total = time.monotonic() - overall_start

        print(f"  Documents : {len(docs)}")
        print(f"  Companies : {', '.join(sorted(companies))}")
        print(f"  Chunks    : {total_chunks} (BM25 index: {chunk_count})")
        print(f"  Time      : {elapsed_total:.1f}s")
        print()
        print("Ready — open http://localhost:5173")


if __name__ == "__main__":
    main()
