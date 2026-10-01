.PHONY: install test lint check demo eval site serve clean

install:
	python3 -m venv .venv
	.venv/bin/pip install -q -e ".[dev]"

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check src tests

check: test lint

# Build a small database from the captured fixtures and score it.
# Needs no network. This is the fastest way to see the tool work.
demo:
	.venv/bin/python scripts/demo.py

# Measure the extractor against the hand-labelled cases in eval/cases.
# Needs no network and no profile. This is the accuracy number, not a claim.
eval:
	.venv/bin/bidscout eval

# Rebuild the demo database and the JSON the published page reads.
# Needs no network. Run this whenever the extractor or the rules change.
site: demo
	.venv/bin/bidscout --db data/demo.sqlite3 --profile profile.example.yaml \
		export --out docs/data.json

# Look at the page the way GitHub Pages serves it. A browser will not fetch
# data.json over file://, so the folder has to go over HTTP.
serve:
	@echo "http://localhost:8000"
	.venv/bin/python -m http.server 8000 --directory docs

clean:
	rm -rf .venv .pytest_cache .ruff_cache **/__pycache__
