.PHONY: install test lint check ingest site demo demo-site eval serve docs clean

# The venv keeps its executables in Scripts/ on Windows and bin/ elsewhere.
ifeq ($(OS),Windows_NT)
  BIN := .venv/Scripts
  PYTHON_BOOT := py -3
else
  BIN := .venv/bin
  PYTHON_BOOT := python3
endif

DB ?= data/bidscout.sqlite3
PROFILE ?= config/profile.example.yaml

install:
	$(PYTHON_BOOT) -m venv .venv
	$(BIN)/pip install -q -e ".[dev]"

test:
	$(BIN)/pytest -q

lint:
	$(BIN)/ruff check src tests

check: test lint

# --- the pipeline ----------------------------------------------------------
#
#   portal --watch/fetch--> landing (SQLite) --score--> landing
#          --dbt build--> warehouse (DuckDB: staging, core, app marts)
#          --export--> site/data.json --> site/index.html
#
# See docs/data-model.md.

# 1. Land yesterday's notices and read their Section 3. Needs the portal.
ingest:
	$(BIN)/bidscout --db $(DB) watch --days 1
	$(BIN)/bidscout --db $(DB) fetch

# 2-4. Score, build the warehouse, and write the page's data from the app marts.
# Needs no network. The page shows the example company unless PROFILE says
# otherwise, and committing site/data.json publishes whatever profile it used.
site:
	$(BIN)/bidscout --db $(DB) --profile $(PROFILE) export --out site/data.json

# The same pipeline over three captured fixtures, for a machine with no portal.
demo:
	$(BIN)/python scripts/demo.py

demo-site: demo
	$(BIN)/bidscout --db data/demo.sqlite3 --profile $(PROFILE) export --out site/data.json

# Measure the extractor against the hand-labelled cases in eval/cases.
eval:
	$(BIN)/bidscout eval

# Look at the page the way GitHub Pages serves it. A browser will not fetch
# data.json over file://, so the folder has to go over HTTP.
serve:
	@echo "http://localhost:8000"
	$(BIN)/python -m http.server 8000 --directory site

# Browse the warehouse: every model, column, test and the lineage graph.
docs:
	$(BIN)/dbt docs generate --project-dir warehouse --profiles-dir warehouse
	$(BIN)/dbt docs serve --project-dir warehouse --profiles-dir warehouse

clean:
	rm -rf .venv .pytest_cache .ruff_cache warehouse/target warehouse/logs **/__pycache__
