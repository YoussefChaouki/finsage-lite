"""
FinSage-Lite — Search Latency Benchmark Script

Measures P50, P95, P99 latency for dense, sparse, and hybrid search modes
across a representative set of 20 financial queries.

Usage:
    python scripts/benchmark_search.py [--api-url URL] [--runs N] [--output FILE]

Requirements: httpx (already in project deps)
Optional:     tqdm (for progress bars)
"""

from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Benchmark queries — 20 representative financial queries
# ---------------------------------------------------------------------------

BENCHMARK_QUERIES = [
    # Factual (8 queries)
    "What is Apple's total revenue in fiscal year 2024?",
    "How many employees does Apple have?",
    "What is the par value of Apple common stock?",
    "Apple net income 2024",
    "operating expenses breakdown",
    "cash and cash equivalents",
    "capital expenditures 2024",
    "shares outstanding",
    # Analytical (8 queries)
    "Compare the risk factors between 2023 and 2024",
    "How did supply chain issues impact Apple's strategy?",
    "What are the main growth drivers according to management?",
    "Why did gross margin change year over year?",
    "Trend in research and development spending",
    "Impact of foreign exchange on revenue",
    "How does Apple manage interest rate risk?",
    "What is the outlook for services segment growth?",
    # Technical financial terms (4 queries)
    "goodwill impairment testing methodology",
    "ASC 606 revenue recognition policy",
    "deferred tax assets valuation allowance",
    "stock-based compensation expense",
]

SEARCH_MODES = ["dense", "sparse", "hybrid"]

TARGETS_MS: dict[str, float] = {
    "dense": 1000.0,
    "sparse": 500.0,
    "hybrid": 2000.0,
}


# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------


def _try_tqdm() -> Any:
    """Return tqdm if available, else None."""
    try:
        from tqdm import tqdm  # type: ignore[import-untyped]

        return tqdm
    except ImportError:
        return None


class _SimplePbar:
    """Minimal fallback progress bar that prints to stdout."""

    def __init__(self, total: int, desc: str = "") -> None:
        self.total = total
        self.desc = desc
        self._n = 0

    def update(self, n: int = 1) -> None:
        self._n += n
        pct = int(100 * self._n / self.total) if self.total else 100
        print(f"\r  {self.desc}: {self._n}/{self.total} ({pct}%)", end="", flush=True)

    def close(self) -> None:
        print()  # newline after bar


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _post_search(
    client: httpx.Client,
    api_url: str,
    query: str,
    mode: str,
    top_k: int = 5,
) -> tuple[float, int]:
    """POST /api/v1/search and return (latency_ms, result_count).

    Retries once on network timeout.  Returns (-1, 0) on permanent failure.
    """
    url = f"{api_url.rstrip('/')}/api/v1/search"
    payload = {"query": query, "search_mode": mode, "top_k": top_k, "use_hyde": False}

    for attempt in range(2):
        try:
            t0 = time.perf_counter()
            resp = client.post(url, json=payload, timeout=30.0)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            if resp.status_code == 200:
                data = resp.json()
                return latency_ms, data.get("total", 0)

            # Non-2xx — record latency but 0 results
            return latency_ms, 0

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            if attempt == 0:
                print(f"\n  [warn] {mode!r} request timed out ({exc}), retrying…")
                continue
            print(f"\n  [error] {mode!r} request failed after retry: {exc}")
            return -1.0, 0
        except httpx.HTTPError as exc:
            print(f"\n  [error] HTTP error for mode={mode!r}: {exc}")
            return -1.0, 0

    return -1.0, 0  # unreachable but satisfies type checker


def _check_api_health(client: httpx.Client, api_url: str) -> dict[str, Any]:
    """GET /api/v1/search/health — returns {} on failure."""
    url = f"{api_url.rstrip('/')}/api/v1/search/health"
    try:
        resp = client.get(url, timeout=10.0)
        if resp.status_code == 200:
            return dict(resp.json())  # type: ignore[arg-type]
    except httpx.HTTPError:
        pass
    return {}


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def _percentile(data: list[float], pct: float) -> float:
    """Return the p-th percentile of *data* using linear interpolation."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    return float(statistics.quantiles(sorted_data, n=100, method="inclusive")[int(pct) - 1])


def _compute_stats(
    latencies: list[float],
    result_counts: list[int],
) -> dict[str, float]:
    valid = [x for x in latencies if x >= 0]
    if not valid:
        return {
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "avg": 0.0,
            "avg_results": 0.0,
            "errors": float(len(latencies) - len(valid)),
        }
    return {
        "p50": _percentile(valid, 50),
        "p95": _percentile(valid, 95),
        "p99": _percentile(valid, 99),
        "avg": statistics.mean(valid),
        "avg_results": statistics.mean(result_counts) if result_counts else 0.0,
        "errors": float(len(latencies) - len(valid)),
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def _status_emoji(p99_ms: float, target_ms: float) -> str:
    return "✅" if p99_ms <= target_ms else "❌"


def _generate_report(
    stats: dict[str, dict[str, float]],
    health: dict[str, Any],
    runs: int,
    output_path: str,
) -> None:
    """Write BENCHMARK.md to *output_path*."""
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    nb_chunks = health.get("bm25_index_size", "unknown")
    os_name = platform.system()

    lines: list[str] = [
        "# FinSage-Lite — Search Latency Benchmarks",
        "",
        f"**Date** : {now}",
        f"**Environnement** : {os_name}, Docker, pgvector",
        f"**Dataset** : {nb_chunks} chunks (AAPL FY2024)",
        f"**Runs par query** : {runs}",
        "",
        "## Résultats",
        "",
        "| Mode    | P50 (ms) | P95 (ms) | P99 (ms) | Avg résultats |",
        "|---------|----------|----------|----------|---------------|",
    ]

    for mode in SEARCH_MODES:
        s = stats.get(mode, {})
        p50 = f"{s.get('p50', 0):.1f}"
        p95 = f"{s.get('p95', 0):.1f}"
        p99 = f"{s.get('p99', 0):.1f}"
        avg_r = f"{s.get('avg_results', 0):.1f}"
        lines.append(f"| {mode:<7} | {p50:>8} | {p95:>8} | {p99:>8} | {avg_r:>13} |")

    lines += [
        "",
        "## Objectifs",
        "",
        "| Mode    | Cible    | Statut |",
        "|---------|----------|--------|",
    ]

    for mode in SEARCH_MODES:
        target = TARGETS_MS[mode]
        p99 = stats.get(mode, {}).get("p99", float("inf"))
        status = _status_emoji(p99, target)
        target_str = f"< {int(target)}ms"
        lines.append(f"| {mode:<7} | {target_str:<8} | {status}     |")

    lines += [
        "",
        "## Notes",
        "",
        "- Index BM25 : in-memory, reconstruit au démarrage",
        "- Dense : pgvector ivfflat cosine, lists=100",
        "- HyDE non inclus dans ces benchmarks (dépend d'Ollama)",
        f"- Queries testées : {len(BENCHMARK_QUERIES)} ({runs} runs each)",
        "",
        "## Détails par mode",
        "",
    ]

    for mode in SEARCH_MODES:
        s = stats.get(mode, {})
        errors = int(s.get("errors", 0))
        total = len(BENCHMARK_QUERIES) * runs
        lines += [
            f"### {mode.capitalize()}",
            f"- Avg: {s.get('avg', 0):.1f} ms",
            f"- Errors: {errors}/{total}",
            "",
        ]

    content = "\n".join(lines) + "\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n  Report written to: {output_path}")


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------


def run_benchmark(api_url: str, runs: int, output: str) -> None:
    """Execute the full benchmark suite and write the report."""
    print("\nFinSage-Lite Search Benchmark")
    print(f"  API URL : {api_url}")
    print(f"  Queries : {len(BENCHMARK_QUERIES)}")
    print(f"  Runs    : {runs} per query")
    print(f"  Output  : {output}")
    print()

    client = httpx.Client()

    # Health check
    print("Checking API health…")
    health = _check_api_health(client, api_url)
    if health:
        print(f"  BM25 index size : {health.get('bm25_index_size', 'n/a')}")
        print(f"  BM25 built      : {health.get('bm25_is_built', 'n/a')}")
        print(f"  HyDE available  : {health.get('hyde_available', 'n/a')}")
    else:
        print("  [warn] Could not reach /api/v1/search/health — continuing anyway")
    print()

    tqdm_cls = _try_tqdm()

    # Collect latencies: mode → list[float]
    latencies: dict[str, list[float]] = defaultdict(list)
    result_counts: dict[str, list[int]] = defaultdict(list)

    total_ops = len(SEARCH_MODES) * len(BENCHMARK_QUERIES) * runs

    pbar: Any
    if tqdm_cls is not None:
        pbar = tqdm_cls(total=total_ops, desc="Benchmarking", unit="req")
    else:
        pbar = _SimplePbar(total=total_ops, desc="Benchmarking")

    try:
        for mode in SEARCH_MODES:
            for query in BENCHMARK_QUERIES:
                for _ in range(runs):
                    lat_ms, n_results = _post_search(client, api_url, query, mode)
                    latencies[mode].append(lat_ms)
                    result_counts[mode].append(n_results)
                    pbar.update(1)
    finally:
        pbar.close()
        client.close()

    # Compute stats
    print("\nResults:")
    print(f"  {'Mode':<10} {'P50 (ms)':>10} {'P95 (ms)':>10} {'P99 (ms)':>10} {'Avg res':>8}")
    print(f"  {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8}")

    stats: dict[str, dict[str, float]] = {}
    for mode in SEARCH_MODES:
        s = _compute_stats(latencies[mode], result_counts[mode])
        stats[mode] = s
        target = TARGETS_MS[mode]
        status = "OK" if s["p99"] <= target else "SLOW"
        print(
            f"  {mode:<10} {s['p50']:>10.1f} {s['p95']:>10.1f} {s['p99']:>10.1f}"
            f" {s['avg_results']:>8.1f}  [{status}]"
        )

    _generate_report(stats, health, runs, output)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FinSage-Lite search latency benchmark",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--api-url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--runs", type=int, default=3, help="Runs per query per mode")
    parser.add_argument("--output", default="BENCHMARK.md", help="Output report path")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_benchmark(api_url=args.api_url, runs=args.runs, output=args.output)
    sys.exit(0)
