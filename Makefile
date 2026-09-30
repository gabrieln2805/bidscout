.PHONY: install test lint check demo eval clean

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

clean:
	rm -rf .venv .pytest_cache .ruff_cache **/__pycache__
