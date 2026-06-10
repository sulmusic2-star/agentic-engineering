# `evals/` — an eval harness that gates AI output before it ships

This is **eval-driven development**: the same discipline as unit tests, applied
to the output of an AI system. Before a candidate "answer" is allowed to ship,
it has to clear a harness. If quality regresses, the build goes red.

Everything here runs on a **toy synthetic dataset** with **no API keys** and
**no network**. The LLM-judge tier is *stubbed* with a deterministic fake so the
whole suite is reproducible in CI.

## What this demonstrates

| Idea | Where |
|---|---|
| **Deterministic checks** (schema / valid URL / valid ISO date) | `checks.py`, Tier 1 |
| **Rubric tier** — LLM-as-judge, here a deterministic stub | `checks.py`, Tier 2 |
| **Composite score** combining the tiers into one verdict | `checks.py`, Tier 3 |
| **CI gate** — exits non-zero if pass rate drops below a threshold | `run_evals.py` |
| **Drift detection** — sample N% of production traffic, flag distribution shift | `drift_check.py` |
| The harness is itself tested | `test_evals.py` |

## The toy domain (zero real data)

Each record is a generic, made-up "claim + its cited source + when it was
checked," labeled with the verdict we expect:

```json
{"id": "ex-001", "claim": "The library opens at 9am on weekdays.",
 "source": "https://example.org/library/hours", "checked_date": "2026-01-15",
 "expected_verdict": "pass"}
```

There are 12 labeled examples in `dataset.jsonl` — 6 that should pass, and 6
that should fail for distinct reasons (missing source, non-URL source, bad date,
empty claim, marketing hype, stale date).

## The three tiers

1. **Deterministic (Tier 1).** Pure code. Are all fields present? Is the source
   a real `http(s)` URL? Is the date a valid ISO `YYYY-MM-DD`? Same answer every
   time, instantly, offline. This catches most bad output cheaply.
2. **Rubric (Tier 2).** Judgement calls — "is this written in neutral,
   verifiable language, or is it marketing hype?" and "is the check fresh?" In
   production you might ask an LLM to grade against a rubric. Here it is a
   **deterministic stub** (`_stub_rubric_judge`) so CI is repeatable. A real
   judge can be swapped in behind `EVAL_USE_REAL_JUDGE=1` — the signature is a
   drop-in match — but it is **off by default** so nothing here needs a key or a
   network.
3. **Composite (Tier 3).** One verdict + a 0..1 score. The rule is strict, like
   a real ship gate: **a deterministic failure is fatal** (a malformed record
   can never "pass"); the rubric only gets a vote once the record is
   structurally valid. Tier 1 is weighted 0.6, Tier 2 0.4.

## Why evals gate the build like unit tests

A unit test pins down deterministic code: change behavior and the test goes red.
But AI output is fuzzy and the failure modes are different — a model can quietly
start citing nothing, emitting malformed dates, or drifting into hype. An eval
harness is the unit-test equivalent for that fuzziness: a labeled dataset plus
graded checks, wired so that **a drop in pass rate fails the build**. It turns
"the AI got worse" from an invisible, gradual regression into a hard, visible
stop — the same safety net unit tests give ordinary code, which is exactly what
you need before putting AI output in front of anyone.

## Run it

```bash
# from this directory:
python -m pytest                # runs test_evals.py (13 tests)
python run_evals.py             # prints the scorecard, exits non-zero if it fails the gate
python run_evals.py --threshold 0.95   # stricter gate
python drift_check.py           # demo: sample production traffic and flag drift
```

No dependencies beyond the Python standard library and `pytest`.
