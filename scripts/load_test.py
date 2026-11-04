"""Concurrent load test against the hosted MCP endpoint.

Fires N parallel `tools/call` requests (the heaviest common operation) and
reports latency percentiles and the error rate — the number behind "handles
concurrent users".

    uv run python scripts/load_test.py --url https://tender-radar-lime.vercel.app/mcp \
        --concurrency 10 --rounds 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time

import httpx

PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "search_tenders",
        "arguments": {"query": "software", "open_only": True, "max_results": 10},
    },
}
HEADERS = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
}


async def one_call(client: httpx.AsyncClient, url: str) -> tuple[float, int, str]:
    start = time.perf_counter()
    try:
        response = await client.post(url, json=PAYLOAD, headers=HEADERS)
        elapsed = time.perf_counter() - start
        body = response.json()
        error = ""
        if response.status_code != 200:
            error = f"http {response.status_code}"
        elif body.get("result", {}).get("isError"):
            error = "tool error"
        return elapsed, response.status_code, error
    except Exception as exc:  # noqa: BLE001 - a load test reports, never raises
        return time.perf_counter() - start, 0, type(exc).__name__


async def run(url: str, concurrency: int, rounds: int) -> int:
    results: list[tuple[float, int, str]] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Warm-up: absorb one cold start so rounds measure steady state.
        await one_call(client, url)
        for round_number in range(1, rounds + 1):
            batch = await asyncio.gather(*(one_call(client, url) for _ in range(concurrency)))
            results.extend(batch)
            worst = max(elapsed for elapsed, _, _ in batch)
            print(f"round {round_number}: {concurrency} parallel calls, slowest {worst:.2f}s")

    latencies = sorted(elapsed for elapsed, _, error in results if not error)
    failures = [(status, error) for _, status, error in results if error]
    total = len(results)
    print(f"\n{total} calls, {len(failures)} failed")
    if failures:
        print("failures:", failures[:10])
    if latencies:
        print(f"p50 {statistics.median(latencies):.2f}s")
        print(f"p95 {latencies[max(0, int(len(latencies) * 0.95) - 1)]:.2f}s")
        print(f"max {latencies[-1]:.2f}s")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://tender-radar-lime.vercel.app/mcp")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps({"url": args.url, "concurrency": args.concurrency, "rounds": args.rounds}))
    return asyncio.run(run(args.url, args.concurrency, args.rounds))


if __name__ == "__main__":
    raise SystemExit(main())
