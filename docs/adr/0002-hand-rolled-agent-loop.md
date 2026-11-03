# ADR-0002: Hand-rolled agent loop instead of a framework

Status: accepted

## Context

The CLI agent exists so evals can run headless and the flagship question has
a scripted, citable answer. Frameworks (pydantic-ai, LangChain) would provide
the loop for free, including native MCP support.

## Decision

Write the loop by hand: ~100 lines in `src/tender_radar/agent/loop.py`, with
the LLM behind a three-method protocol (`src/tender_radar/agent/provider.py`)
so the model is swappable without touching the loop.

## Consequences

- The whole control flow — tool dispatch, citation harvesting, turn budget —
  is readable in one sitting, which is worth more here than framework
  features; this is a portfolio project whose reviewer reads code.
- No framework release cycle in the dependency tree; the MCP SDK and the
  provider SDK are the only moving parts.
- We forgo framework conveniences (retries, streaming, tracing). The eval
  harness's response cache covers the main operational need.
- The loop is testable without any LLM: a scripted provider drives the real
  server over stdio in `tests/test_agent_loop.py`.
