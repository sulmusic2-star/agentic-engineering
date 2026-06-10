"""
checks.py — the three tiers of an eval harness.

The job of this module is to take ONE candidate record (a toy "answer" an AI
system produced) and decide whether it is good enough to ship. We do that in
three clearly separated tiers, from cheapest/strictest to fuzziest:

    Tier 1 — DETERMINISTIC checks
        Pure, boring code. Schema present? Source a real URL? Date a valid
        ISO date? These never call a model, never touch the network, and give
        the SAME answer every time. They are fast and they are where most bad
        output gets caught.

    Tier 2 — RUBRIC tier (LLM-as-judge, here STUBBED)
        Some quality questions are judgement calls ("is this claim written in
        neutral, verifiable language, or is it marketing hype?"). In
        production you might ask an LLM to grade against a rubric. That is slow,
        costs money, and is non-deterministic — bad for CI. So here the judge
        is a *stub*: a pure function that simulates a rubric verdict
        deterministically. A real judge can be swapped in behind an env flag
        (see `rubric_judge`), but the default path stays offline and repeatable.

    Tier 3 — COMPOSITE score
        Combine the tiers into one verdict + a 0..1 score. The rule here is
        simple and strict, mirroring a real ship gate: deterministic failures
        are fatal (a malformed record can never "pass"); the rubric only gets a
        vote once the record is structurally valid.

Every function takes a plain dict and returns plain data, so this file has no
hidden state and is trivial to unit-test.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Config / constants
# --------------------------------------------------------------------------- #

# The fields every well-formed record must contain.
REQUIRED_FIELDS = ("id", "claim", "source", "checked_date")

# A deliberately simple URL shape check. We are NOT trying to validate every
# legal URL on earth — just to reject obviously-not-a-URL strings like "" or
# "not-a-real-url". Keeping it readable beats being clever here.
_URL_RE = re.compile(r"^https?://[^\s]+\.[^\s]+", re.IGNORECASE)

# How old a `checked_date` may be before the rubric tier considers it stale.
# Lives here as a named constant so the "why" is obvious and easy to tune.
FRESHNESS_WINDOW_DAYS = 365 * 3  # ~3 years

# "Today" for freshness math. Pinned via env so tests/CI are reproducible and
# don't silently start failing as the calendar advances. Defaults to a fixed
# date rather than the real clock for exactly that reason.
_TODAY = _dt.date.fromisoformat(os.environ.get("EVAL_TODAY", "2026-06-10"))

# Hype / non-verifiable words the stub rubric penalizes. A real LLM judge would
# reason about this far more richly; this is a deterministic stand-in.
_HYPE_WORDS = (
    "best", "amazing", "miracle", "guaranteed", "ever", "unbelievable",
    "incredible", "revolutionary", "perfect",
)


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #

@dataclass
class CheckResult:
    """The full verdict for one record, with a breadcrumb trail of reasons.

    `score` is 0..1. `verdict` is "pass" or "fail". `reasons` explains every
    deduction so a scorecard (or a human in review) can see *why*.
    """

    verdict: str
    score: float
    deterministic_ok: bool
    rubric_ok: bool
    reasons: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Tier 1 — deterministic checks (pure code, no model, no network)
# --------------------------------------------------------------------------- #

def check_schema(record: dict) -> list[str]:
    """Return a list of problems with the record's shape. Empty list == clean."""
    problems: list[str] = []

    # Every required field must be present AND non-empty (after stripping).
    for fieldname in REQUIRED_FIELDS:
        value = record.get(fieldname)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            problems.append(f"missing or empty field: {fieldname!r}")

    return problems


def check_source_is_url(record: dict) -> list[str]:
    """The cited source must look like a real http(s) URL."""
    source = record.get("source", "")
    if not isinstance(source, str) or not _URL_RE.match(source.strip()):
        return [f"source is not a valid URL: {source!r}"]
    return []


def check_date_is_iso(record: dict) -> list[str]:
    """`checked_date` must be a real calendar date in ISO YYYY-MM-DD form."""
    raw = record.get("checked_date", "")
    if not isinstance(raw, str):
        return [f"checked_date is not a string: {raw!r}"]
    try:
        # fromisoformat is strict about YYYY-MM-DD, which is exactly what we want.
        _dt.date.fromisoformat(raw.strip())
    except ValueError:
        return [f"checked_date is not ISO YYYY-MM-DD: {raw!r}"]
    return []


def run_deterministic(record: dict) -> list[str]:
    """Run every Tier-1 check and collect all problems.

    We intentionally run ALL checks (instead of bailing on the first failure)
    so the scorecard can report every issue at once — much friendlier when a
    human is debugging why a record was rejected.
    """
    problems: list[str] = []
    problems += check_schema(record)
    problems += check_source_is_url(record)
    problems += check_date_is_iso(record)
    return problems


# --------------------------------------------------------------------------- #
# Tier 2 — rubric tier (LLM-as-judge), STUBBED by default
# --------------------------------------------------------------------------- #

def _stub_rubric_judge(record: dict) -> tuple[bool, list[str]]:
    """A DETERMINISTIC fake "LLM judge".

    This stands in for "ask a model to grade this claim against a rubric."
    It is a pure function: same input -> same output, every time, offline.
    That is the whole point — CI must be reproducible.

    Our toy rubric has two criteria a structurally-valid record can still fail:
      1. Neutral, verifiable language (no marketing hype, not shouting).
      2. Freshness — the check isn't ancient.

    A real judge would be far more nuanced; the SHAPE (criteria -> verdict +
    reasons) is what we are demonstrating.
    """
    reasons: list[str] = []
    claim = str(record.get("claim", ""))
    lowered = claim.lower()

    # Criterion 1a: marketing / non-verifiable hype words.
    hits = sorted({w for w in _HYPE_WORDS if w in lowered})
    if hits:
        reasons.append(f"rubric: claim uses hype/non-verifiable language: {hits}")

    # Criterion 1b: shouting (lots of exclamation marks) reads as promo, not fact.
    if claim.count("!") >= 2:
        reasons.append("rubric: claim is written like an ad (multiple '!')")

    # Criterion 2: freshness. If the date is valid but older than the window,
    # the rubric flags it as stale. (Invalid dates are already a Tier-1 fail.)
    raw_date = str(record.get("checked_date", "")).strip()
    try:
        checked = _dt.date.fromisoformat(raw_date)
        age_days = (_TODAY - checked).days
        if age_days > FRESHNESS_WINDOW_DAYS:
            reasons.append(
                f"rubric: source check is stale ({age_days} days old, "
                f"window is {FRESHNESS_WINDOW_DAYS})"
            )
    except ValueError:
        # Date already handled by Tier 1; the rubric stays silent about it.
        pass

    return (len(reasons) == 0, reasons)


def rubric_judge(record: dict) -> tuple[bool, list[str]]:
    """Tier-2 entry point.

    Default: the deterministic stub above (offline, free, repeatable).

    Optional: set EVAL_USE_REAL_JUDGE=1 to route to a real LLM judge instead.
    We keep that path *off by default* and isolated here so the rest of the
    harness never has to care which judge is live. The real implementation is
    intentionally left as a stub-raise: wiring an actual model call (and an API
    key) is an environment concern, not something CI should ever depend on.
    """
    if os.environ.get("EVAL_USE_REAL_JUDGE") == "1":  # pragma: no cover
        return _real_rubric_judge(record)
    return _stub_rubric_judge(record)


def _real_rubric_judge(record: dict) -> tuple[bool, list[str]]:  # pragma: no cover
    """Placeholder for a real LLM-as-judge call.

    Deliberately NOT implemented: a live model call needs an API key and a
    network, which would make the eval suite non-deterministic and unable to
    run offline in CI. In a real project you would, behind this flag, call your
    model with a rubric prompt and parse a structured verdict back out. The
    signature matches the stub so it is a drop-in swap.
    """
    raise NotImplementedError(
        "Real LLM judge is intentionally not wired up. The stub judge is used "
        "by default so evals run offline and reproducibly. To experiment, "
        "implement a model call here and set EVAL_USE_REAL_JUDGE=1."
    )


# --------------------------------------------------------------------------- #
# Tier 3 — composite score
# --------------------------------------------------------------------------- #

def score_record(record: dict) -> CheckResult:
    """Combine all tiers into one pass/fail verdict and a 0..1 score.

    Scoring rule (simple and strict, like a real ship gate):
      * Tier 1 is worth 0.6 of the score, Tier 2 is worth 0.4.
      * A Tier-1 (deterministic) failure is FATAL: verdict is always "fail",
        no matter how the rubric feels. A structurally broken record must never
        be shippable. (It still earns the 0.4 rubric portion if the rubric is
        happy, so the score is informative, but the verdict stays "fail".)
      * If Tier 1 passes, the rubric decides the verdict.
    """
    det_problems = run_deterministic(record)
    deterministic_ok = len(det_problems) == 0

    rubric_ok, rubric_reasons = rubric_judge(record)

    # Weighted score: each tier contributes its weight only if it passed.
    score = (0.6 if deterministic_ok else 0.0) + (0.4 if rubric_ok else 0.0)

    # Verdict: deterministic failure is fatal; otherwise the rubric rules.
    verdict = "pass" if (deterministic_ok and rubric_ok) else "fail"

    return CheckResult(
        verdict=verdict,
        score=round(score, 3),
        deterministic_ok=deterministic_ok,
        rubric_ok=rubric_ok,
        reasons=det_problems + rubric_reasons,
    )
