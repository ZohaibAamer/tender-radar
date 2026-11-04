"""CLI: ask the agent a question.

    uv run python -m tender_radar.agent "which open tenders fit a 50-person
    UK data consultancy?"

Requires GEMINI_API_KEY (free tier is fine).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .loop import run_agent
from .provider import GeminiProvider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tender_radar.agent")
    parser.add_argument("question")
    parser.add_argument("--model", default="gemini-3.8-flash")
    args = parser.parse_args(argv)

    result = asyncio.run(run_agent(args.question, GeminiProvider(model=args.model)))
    print(result.answer)
    if result.citations:
        print("\nSources:")
        for citation in result.citations:
            print(f"- {citation['tender_ref']}: {citation['title']}\n  {citation['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
