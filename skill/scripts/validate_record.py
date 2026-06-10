#!/usr/bin/env python3
"""
validate_record.py — the deterministic core of the "validate-a-structured-record" skill.

WHY THIS IS A SCRIPT, NOT A PROMPT
----------------------------------
An Agent Skill is a playbook. Most of it is natural-language instructions the
agent reads and reasons about. But some steps must be EXACT every single time —
"is this a valid ISO date?", "is this a real URL?", "are all required fields
present?". You do not want a language model eyeballing a date string and being
right 98% of the time. You want code that is right 100% of the time. So the
skill hands those steps to this script and trusts its structured output.

WHAT IT DOES
------------
Reads one JSON record (from a file, or from stdin) and validates it against a
small, generic schema. Prints a JSON verdict and sets its exit code so the
calling agent can branch on success/failure without parsing prose:

    exit 0  -> record is valid
    exit 1  -> record is invalid (see "errors" in the JSON output)
    exit 2  -> the input itself was not usable (bad JSON, no input)

USAGE
-----
    python validate_record.py path/to/record.json
    cat record.json | python validate_record.py
    python validate_record.py --demo        # validate a built-in good example

The record shape (intentionally generic — no domain meaning):
    {
        "id":           non-empty string,
        "claim":        non-empty string,
        "source":       an http(s) URL,
        "checked_date": an ISO date, YYYY-MM-DD
    }
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys

# Required fields and a simple, readable URL shape check. Same philosophy as a
# real validator: reject the obviously-wrong, stay easy to read and audit.
REQUIRED_FIELDS = ("id", "claim", "source", "checked_date")
_URL_RE = re.compile(r"^https?://[^\s]+\.[^\s]+", re.IGNORECASE)

_DEMO_RECORD = {
    "id": "demo-1",
    "claim": "The reading room seats 60 people.",
    "source": "https://example.org/reading-room",
    "checked_date": "2026-03-01",
}


def validate(record: dict) -> list[str]:
    """Return a list of human-readable errors. Empty list == the record is valid.

    Pure function: no I/O, no global state, deterministic. Easy to unit-test and
    easy for the skill to rely on.
    """
    errors: list[str] = []

    if not isinstance(record, dict):
        return [f"record must be a JSON object, got {type(record).__name__}"]

    # 1. Required fields present and non-empty.
    for field in REQUIRED_FIELDS:
        value = record.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            errors.append(f"missing or empty field: '{field}'")

    # 2. Source must look like a real http(s) URL.
    source = record.get("source", "")
    if not isinstance(source, str) or not _URL_RE.match(source.strip()):
        errors.append(f"'source' is not a valid http(s) URL: {source!r}")

    # 3. checked_date must be a real ISO calendar date (YYYY-MM-DD).
    raw_date = record.get("checked_date", "")
    if isinstance(raw_date, str):
        try:
            _dt.date.fromisoformat(raw_date.strip())
        except ValueError:
            errors.append(f"'checked_date' is not ISO YYYY-MM-DD: {raw_date!r}")
    else:
        errors.append(f"'checked_date' must be a string, got {type(raw_date).__name__}")

    return errors


def _read_input(args: argparse.Namespace) -> dict:
    """Load the record from --demo, a file path, or stdin. Raises on bad input."""
    if args.demo:
        return dict(_DEMO_RECORD)
    if args.path:
        with open(args.path, encoding="utf-8") as fh:
            return json.load(fh)
    # Fall back to stdin so the script composes nicely in a pipeline.
    if sys.stdin.isatty():
        raise ValueError("no input: pass a file path, pipe JSON via stdin, or use --demo")
    return json.loads(sys.stdin.read())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministically validate one structured record.")
    parser.add_argument("path", nargs="?", help="path to a JSON record file (optional; else stdin)")
    parser.add_argument("--demo", action="store_true", help="validate a built-in valid example")
    args = parser.parse_args(argv)

    # Stage 1: get usable input, or exit 2.
    try:
        record = _read_input(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "stage": "input", "error": str(exc)}, indent=2))
        return 2

    # Stage 2: validate, and report a structured verdict.
    errors = validate(record)
    verdict = {
        "ok": len(errors) == 0,
        "id": record.get("id") if isinstance(record, dict) else None,
        "errors": errors,
    }
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
