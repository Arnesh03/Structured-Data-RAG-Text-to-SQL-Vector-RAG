.PHONY: help install setup rebuild api web dev cli demo stats gradio test clean

VENV ?= .venv
PY   := $(VENV)/bin/python

help:     ## list the available targets
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## create the venv, install Python deps, install web deps
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements-dev.txt
	npm install --prefix web

setup:    ## clean the CSV, build the SQLite DB and the FAISS index
	$(PY) cli.py --setup

rebuild:  ## rebuild every artifact from the raw CSV
	$(PY) cli.py --setup --force

api:      ## run the FastAPI backend (port 8010)
	$(PY) server.py

web:      ## run the Next.js frontend (port 3000) - needs `make api` too
	npm run dev --prefix web

dev:      ## run the backend and the frontend together
	@$(MAKE) api & $(MAKE) web

cli:      ## interactive terminal chat
	$(PY) cli.py

demo:     ## run scripted questions across both routes
	$(PY) cli.py --demo

stats:    ## print the dataset aggregates
	$(PY) cli.py --stats

gradio:   ## run the dependency-light Gradio UI instead of Next.js
	$(PY) app.py

test:     ## run the offline test suite
	$(PY) -m pytest

clean:    ## remove generated data and caches
	rm -rf data/healthcare.db data/healthcare_clean.csv \
	       data/preprocessing_report.json data/faiss_index data/policies
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache web/.next
