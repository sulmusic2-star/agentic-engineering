"""
run_evals.py — run the whole eval suite and gate the build.

This is the "evals are unit tests for AI output" pattern. We:
  1. Load the labeled dataset (each record has an `expected_verdict`).
  2. Score every record with the three-tier harness in checks.py.
  3. Compare our verdict to the expected label -> the example "passes" the eval
     if we agreed with the label.
  4. Print a human-readable scorecard.
  5. EXIT NON-ZERO if the pass rate falls below a threshold.

Step 5 is the important one: wired into CI, it turns "the AI quality regressed"
into a red build, exactly like a failing unit test. Run it directly:

    python run_evals.py
    python run_evals.py --threshold 0.95   # stricter gate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from checks import score_record

# Default gate: at least 90% of labeled examples must come out as we expect.
DEFAULT_THRESHOLD = 0.90

DATASET_PATH = Path(__file__).parent / "dataset.jsonl"


def load_dataset(path: Path = DATASET_PATH) -> list[dict]:
    """Read a .jsonl file (one JSON object per line) into a list of dicts."""
    records: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue  # tolerate blank lines
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"bad JSON on line {line_no} of {path}: {exc}") from exc
    return records


def evaluate(records: list[dict]) -> tuple[list[dict], float]:
    """Score every record and tag whether we matched its expected verdict.

    Returns (rows, pass_rate) where each row is a small dict ready to print.
    """
    rows: list[dict] = []
    matched = 0

    for rec in records:
        result = score_record(rec)
        expected = rec.get("expected_verdict")
        # The eval "passes" when our harness's verdict equals the human label.
        ok = result.verdict == expected
        if ok:
            matched += 1
        rows.append(
            {
                "id": rec.get("id", "?"),
                "expected": expected,
                "got": result.verdict,
                "score": result.score,
                "match": ok,
                "reasons": result.reasons,
            }
        )

    pass_rate = matched / len(records) if records else 0.0
    return rows, pass_rate


def print_scorecard(rows: list[dict], pass_rate: float, threshold: float) -> None:
    """Pretty-print a scorecard table plus a summary line."""
    print("\n=== EVAL SCORECARD ===")
    print(f"{'id':<8} {'expected':<9} {'got':<6} {'score':<6} {'match'}")
    print("-" * 44)
    for row in rows:
        flag = "ok" if row["match"] else "XX"
        print(
            f"{row['id']:<8} {row['expected']:<9} {row['got']:<6} "
            f"{row['score']:<6} {flag}"
        )
        # On a mismatch, show why so the failure is actionable, not mysterious.
        if not row["match"] and row["reasons"]:
            for reason in row["reasons"]:
                print(f"         - {reason}")

    passed = sum(1 for r in rows if r["match"])
    total = len(rows)
    print("-" * 44)
    print(f"passed {passed}/{total}  pass_rate={pass_rate:.2%}  threshold={threshold:.0%}")


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code (0 = gate passed)."""
    parser = argparse.ArgumentParser(description="Run the eval suite and gate the build.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"minimum pass rate to allow the build (default {DEFAULT_THRESHOLD}).",
    )
    args = parser.parse_args(argv)

    records = load_dataset()
    rows, pass_rate = evaluate(records)
    print_scorecard(rows, pass_rate, args.threshold)

    # THE GATE. Below threshold -> non-zero exit -> red CI build.
    if pass_rate < args.threshold:
        print(f"\nGATE FAILED: pass_rate {pass_rate:.2%} < threshold {args.threshold:.0%}")
        return 1

    print(f"\nGATE PASSED: pass_rate {pass_rate:.2%} >= threshold {args.threshold:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
