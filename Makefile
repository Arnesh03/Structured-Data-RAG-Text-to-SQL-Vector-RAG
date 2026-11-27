.PHONY: help install setup rebuild api web dev cli demo stats gradio test clean \
        eval eval-grid eval-score eval-report eval-ablations eval-ci eval-stats \
        eval-seed eval-promote eval-judge-export eval-kappa eval-save-baseline

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

# ── Evaluation harness ────────────────────────────────────────────────
# Running and scoring are separate: `eval` records raw traces, `eval-score`
# grades them. Adding a metric re-scores past runs without re-running anything.

eval:           ## run the baseline config over the golden set
	$(PY) -m evalkit.runner --config configs/baseline.yaml --score

eval-grid:      ## run every config: baseline plus each one-variable ablation
	$(PY) -m evalkit.runner --score

eval-score:     ## re-score the latest baseline run (no pipeline re-run)
	$(PY) -m evalkit.score

eval-report:    ## render a markdown report for the latest run
	$(PY) -m evalkit.report

eval-ablations: ## render the ablation table across every finished run
	$(PY) -c "from evalkit.store import TraceStore; from evalkit.report import compare; \
	          compare([r['run_id'] for r in reversed(TraceStore().list_runs()) if r['finished_at']])"

eval-stats:     ## print the golden set composition
	$(PY) -c "from evalkit.dataset import GoldenSet; print(GoldenSet.load().summary())"

eval-ci:        ## stratified 20-question subset, deterministic metrics, then gate
	$(PY) -m evalkit.runner --config configs/baseline.yaml --sample 20
	$(PY) -m evalkit.score --no-judge
	$(PY) -m evalkit.gate

eval-seed:      ## generate candidate questions for manual review
	$(PY) -m evalkit.seed

eval-promote:   ## merge reviewed candidates into the golden set
	$(PY) -m evalkit.seed --promote

eval-judge-export: ## export 50 answers to label by hand, judge verdict hidden
	$(PY) -m evalkit.judge_validate --export 50

eval-kappa:     ## report judge-vs-human agreement from your labels
	$(PY) -m evalkit.judge_validate

eval-save-baseline: ## commit the latest run's metrics as the CI gate baseline
	$(PY) -m evalkit.report --save-baseline
