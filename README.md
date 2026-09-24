# Neutral

Middleware that sits between a person and an LLM. Before the prompt reaches the model it
removes or restructures signals about *who is asking* that are not relevant to the question.
After the answer comes back it restores readable language.

**The product is not the rewriting. The product is the evidence that the rewriting changes
outcomes.** The evaluation harness is therefore the primary deliverable and the pipeline has
to satisfy it.

Two failures are being measured:

1. **Demographic bias** - the answer changes based on apparent race, gender, age, nationality
   or seniority when it should not.
2. **Sycophancy** - a more favourable assessment when the model can tell the asker is also the
   author or subject of what is being assessed.

First market: HR and employment decisions - performance reviews, hiring notes, promotion
rationales.

## Status

Phase 1: evaluation harness and baseline, **no Neutral in the path**. See DECISIONS.md for the
phase plan, BASELINE.md for the measured number and the threshold that was registered before
Neutral existed.

## Layout

    eval/           harness: client, dataset, scoring, runner
    tests/          offline pytest checks, no network
    results/        baseline JSON, dataset snapshot, raw answers (results/raw is gitignored)
    reports/        readable HTML report and the live log
    bench.html      live dashboard; point it at reports/live.log during a run
    BASELINE.md     the number, its confidence interval, and the pre-registered threshold
    DECISIONS.md    architecture decisions and anything deliberately deferred

## Setup

    uv sync                       # creates .venv and installs pytest + ruff
    copy .env.example .env        # then fill in the key

## Run

    uv run python -m eval.probe                   # per-model latency and token check
    uv run pytest                                 # offline checks, no API calls
    uv run python -m eval.run_eval --limit 2      # cheap smoke run, writes nothing
    uv run python -m eval.run_eval                # the experiment; writes BASELINE.md

While a run is in progress, serve this folder and open the live page:

    python -m http.server 8000
    # http://localhost:8000/bench.html?src=reports/live.log

