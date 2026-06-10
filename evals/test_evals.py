"""
test_evals.py — pytest tests proving the checks and the gate behave.

These tests are the "evals of the eval harness." They prove two things a
reviewer cares about:
  * The shipped dataset passes the gate (green build today).
  * Injecting a bad record drops the pass rate and trips the gate (the gate can
    actually fail — a gate that can't fail isn't a gate).

Run from this directory:
    python -m pytest
"""

from __future__ import annotations

import checks
import run_evals
from checks import score_record


# --------------------------------------------------------------------------- #
# Tier 1 — deterministic checks
# --------------------------------------------------------------------------- #

def _good_record() -> dict:
    """A canonical well-formed, non-hype, fresh record."""
    return {
        "id": "t-good",
        "claim": "The office opens at 8am.",
        "source": "https://example.org/office/hours",
        "checked_date": "2026-01-01",
    }


def test_good_record_passes_all_tiers():
    result = score_record(_good_record())
    assert result.verdict == "pass"
    assert result.deterministic_ok is True
    assert result.rubric_ok is True
    assert result.score == 1.0  # 0.6 + 0.4


def test_missing_source_fails_deterministically():
    rec = _good_record() | {"source": ""}
    result = score_record(rec)
    assert result.verdict == "fail"
    assert result.deterministic_ok is False
    assert any("source" in r for r in result.reasons)


def test_bad_url_fails_deterministically():
    rec = _good_record() | {"source": "not-a-real-url"}
    result = score_record(rec)
    assert result.verdict == "fail"
    assert result.deterministic_ok is False


def test_non_iso_date_fails_deterministically():
    rec = _good_record() | {"checked_date": "01-02-2026"}
    result = score_record(rec)
    assert result.verdict == "fail"
    assert result.deterministic_ok is False


def test_empty_claim_fails_deterministically():
    rec = _good_record() | {"claim": ""}
    result = score_record(rec)
    assert result.verdict == "fail"
    assert result.deterministic_ok is False


# --------------------------------------------------------------------------- #
# Tier 2 — rubric stub
# --------------------------------------------------------------------------- #

def test_hype_language_fails_rubric_not_determinism():
    # Structurally valid, but full of hype -> deterministic OK, rubric fails.
    rec = _good_record() | {"claim": "the best guaranteed amazing miracle ever!!!"}
    result = score_record(rec)
    assert result.deterministic_ok is True
    assert result.rubric_ok is False
    assert result.verdict == "fail"
    # It still earns the deterministic 0.6 portion of the score.
    assert result.score == 0.6


def test_stale_date_fails_rubric():
    rec = _good_record() | {"checked_date": "2010-01-01"}
    result = score_record(rec)
    assert result.deterministic_ok is True  # date is valid ISO...
    assert result.rubric_ok is False        # ...but too old for the window
    assert result.verdict == "fail"


def test_rubric_judge_is_deterministic():
    # The whole reason the judge is stubbed: same input -> same output, always.
    rec = _good_record() | {"claim": "the best ever!!!"}
    first = checks.rubric_judge(rec)
    second = checks.rubric_judge(rec)
    assert first == second


# --------------------------------------------------------------------------- #
# Tier 3 / the GATE
# --------------------------------------------------------------------------- #

def test_shipped_dataset_passes_the_gate():
    """The dataset committed to the repo should make the gate pass today."""
    exit_code = run_evals.main(["--threshold", str(run_evals.DEFAULT_THRESHOLD)])
    assert exit_code == 0


def test_dataset_labels_all_match_harness():
    """Every labeled example's expected verdict matches what the harness says.

    This is stricter than the gate (which tolerates a few misses): it proves the
    dataset and the checks are actually in agreement, so the gate has headroom.
    """
    records = run_evals.load_dataset()
    rows, pass_rate = run_evals.evaluate(records)
    mismatches = [r for r in rows if not r["match"]]
    assert mismatches == [], f"unexpected label mismatches: {mismatches}"
    assert pass_rate == 1.0


def test_injected_bad_record_trips_the_gate(monkeypatch):
    """Inject a record the harness will misjudge and confirm the gate fails.

    We monkeypatch the dataset loader to return the real dataset PLUS a poisoned
    record: it is malformed (no source) yet mislabeled as 'pass'. The harness
    will (correctly) call it 'fail', disagreeing with the label, which drives the
    pass rate below threshold -> the gate must return non-zero.
    """
    real = run_evals.load_dataset()
    poisoned = real + [
        # Mislabeled on purpose: claims to be a 'pass' but has no source.
        {"id": "poison", "claim": "x", "source": "", "checked_date": "2026-01-01",
         "expected_verdict": "pass"},
        {"id": "poison2", "claim": "y", "source": "bad", "checked_date": "nope",
         "expected_verdict": "pass"},
        {"id": "poison3", "claim": "", "source": "", "checked_date": "",
         "expected_verdict": "pass"},
    ]
    monkeypatch.setattr(run_evals, "load_dataset", lambda *a, **k: poisoned)

    # With a strict threshold, the three injected mismatches must trip the gate.
    exit_code = run_evals.main(["--threshold", "0.99"])
    assert exit_code == 1


# --------------------------------------------------------------------------- #
# Drift check
# --------------------------------------------------------------------------- #

def test_drift_check_flags_skewed_stream():
    from drift_check import _demo_streams, check_drift

    reference, production = _demo_streams()
    report = check_drift(reference, production, sample_rate=1.0, tolerance=0.25)
    # The demo production stream is mostly malformed, so it must look drifted.
    assert report["drift_detected"] is True
    assert report["distance"] > 0.25


def test_drift_check_no_drift_when_streams_match():
    from drift_check import check_drift

    same = [
        {"id": f"r-{i}", "claim": "a plain factual statement",
         "source": "https://example.org/a", "checked_date": "2026-01-01"}
        for i in range(10)
    ]
    report = check_drift(same, list(same), sample_rate=1.0, tolerance=0.25)
    assert report["drift_detected"] is False
    assert report["distance"] == 0.0
