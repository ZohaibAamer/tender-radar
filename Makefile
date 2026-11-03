# Shortcuts for every workflow in the README. Run `make help` for the list.

DBT := DBT_PROFILES_DIR=dbt uv run dbt
SINCE ?= $(shell date -v-30d +%Y-%m-%d 2>/dev/null || date -d '30 days ago' +%Y-%m-%d)

.PHONY: help install ingest warehouse dedupe test lint evals fixture-warehouse inspector agent

help: ## list available targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

install: ## create the environment (uv sync)
	uv sync

ingest: ## fetch live notices from all three portals (SINCE=YYYY-MM-DD)
	uv run python -m tender_radar.ingest --source all --since $(SINCE)

warehouse: ## build the DuckDB warehouse with dbt
	$(DBT) deps --project-dir dbt
	$(DBT) build --project-dir dbt

dedupe: ## compute cross-portal duplicate links
	uv run python -m tender_radar.dedupe

lint: ## ruff over the whole repo
	uv run ruff check .

test: lint ## tier-1 checks: lint + the deterministic test suite
	uv run pytest

fixture-warehouse: ## build the frozen eval fixture's warehouse
	TENDER_RADAR_DATA_DIR=$(CURDIR)/fixtures $(DBT) deps --project-dir dbt
	TENDER_RADAR_DATA_DIR=$(CURDIR)/fixtures $(DBT) build --project-dir dbt

evals: ## run the 52-question agent eval suite (needs GEMINI_API_KEY)
	uv run python evals/harness.py

inspector: ## open the MCP server in the official Inspector UI
	npx @modelcontextprotocol/inspector uv run tender-radar-mcp

agent: ## ask the CLI agent a question: make agent Q="which tenders fit ...?"
	uv run python -m tender_radar.agent "$(Q)"
