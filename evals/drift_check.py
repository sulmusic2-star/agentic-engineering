"""
drift_check.py — a tiny demo of production drift detection by sampling.

Evals gate what you ship. But once a system is LIVE, the *inputs* drift: the
mix of records flowing through production slowly stops looking like the data you
designed and tested against. Drift detection is the early-warning system.

This is a deliberately small, dependency-free illustration of the idea:
  1. Take a "reference" distribution (what we expect, e.g. from the eval set).
  2. Sample N% of a stream of "production" records.
  3. Compare the sample's distribution of some feature to the reference.
  4. Flag drift if the gap exceeds a tolerance.

We measure the distribution over a single categorical feature — the verdict our
harness assigns — using total variation distance (half the sum of absolute
differences in category proportions). It is easy to explain and needs no numpy.

Run it:
    python drift_check.py
"""

from __future__ import annotations

import argparse
import random
from collections import Counter

from checks import score_record


def proportions(records: list[dict]) -> dict[str, float]:
    """Compute the fraction of records that land in each verdict bucket."""
    counts = Counter(score_record(r).verdict for r in records)
    total = sum(counts.values()) or 1  # avoid divide-by-zero on empty input
    return {verdict: n / total for verdict, n in counts.items()}


def total_variation_distance(p: dict[str, float], q: dict[str, float]) -> float:
    """Distance between two categorical distributions, in [0, 1].

    0.0 means identical; 1.0 means completely disjoint. We use the standard
    total-variation definition: half the sum of absolute differences across all
    categories present in either distribution.
    """
    categories = set(p) | set(q)
    return 0.5 * sum(abs(p.get(c, 0.0) - q.get(c, 0.0)) for c in categories)


def sample_stream(stream: list[dict], rate: float, seed: int = 0) -> list[dict]:
    """Keep each record with probability `rate` (so we inspect ~rate of traffic).

    Sampling — instead of checking every record — is what makes monitoring cheap
    enough to run continuously in production. A fixed seed keeps this demo
    reproducible.
    """
    rng = random.Random(seed)
    return [r for r in stream if rng.random() < rate]


def check_drift(
    reference: list[dict],
    production_stream: list[dict],
    sample_rate: float = 0.5,
    tolerance: float = 0.25,
    seed: int = 0,
) -> dict:
    """Sample the production stream and report whether it has drifted.

    Returns a small report dict (so it is easy to test and to print).
    """
    sample = sample_stream(production_stream, sample_rate, seed=seed)
    ref_dist = proportions(reference)
    sample_dist = proportions(sample)
    distance = total_variation_distance(ref_dist, sample_dist)

    return {
        "sample_size": len(sample),
        "reference_distribution": ref_dist,
        "sample_distribution": sample_dist,
        "distance": round(distance, 3),
        "tolerance": tolerance,
        "drift_detected": distance > tolerance,
    }


def _demo_streams() -> tuple[list[dict], list[dict]]:
    """Build a clean reference set and a deliberately-skewed production stream.

    The production stream is stuffed with malformed records (missing source) so
    its verdict mix tilts hard toward "fail" — exactly the kind of shift drift
    detection should catch.
    """
    reference = [
        {"id": f"ref-{i}", "claim": "a plain factual statement",
         "source": "https://example.org/a", "checked_date": "2026-01-01"}
        for i in range(10)
    ]
    # 8 broken (no source) + 2 good -> a very different distribution.
    production = [
        {"id": f"prod-bad-{i}", "claim": "a plain factual statement",
         "source": "", "checked_date": "2026-01-01"}
        for i in range(8)
    ] + [
        {"id": f"prod-ok-{i}", "claim": "a plain factual statement",
         "source": "https://example.org/a", "checked_date": "2026-01-01"}
        for i in range(2)
    ]
    return reference, production


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Demo: sample production traffic and flag drift.")
    parser.add_argument("--sample-rate", type=float, default=0.5)
    parser.add_argument("--tolerance", type=float, default=0.25)
    args = parser.parse_args(argv)

    reference, production = _demo_streams()
    report = check_drift(
        reference, production, sample_rate=args.sample_rate, tolerance=args.tolerance
    )

    print("\n=== DRIFT CHECK (demo) ===")
    print(f"sampled {report['sample_size']} of {len(production)} production records "
          f"(rate={args.sample_rate})")
    print(f"reference distribution: {report['reference_distribution']}")
    print(f"sample distribution:    {report['sample_distribution']}")
    print(f"distance={report['distance']}  tolerance={report['tolerance']}")
    print("DRIFT DETECTED" if report["drift_detected"] else "no significant drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
