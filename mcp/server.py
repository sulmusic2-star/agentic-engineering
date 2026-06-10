"""
server.py — a tiny Model Context Protocol (MCP) server.

WHAT THIS IS
------------
MCP is an open protocol that lets an AI agent (the "client" — e.g. Claude
Desktop or an SDK client) talk to external "servers" that expose capabilities.
A server can offer three kinds of primitive; this one focuses on the first:

    * tools      — actions the agent can CALL (functions with typed args).
    * resources  — read-only data the agent can FETCH (like files/URLs).
    * prompts    — reusable prompt templates the agent can use.

This server exposes two clearly-bounded TOOLS over a small synthetic dataset of
generic "claim" records. The tool *descriptions* are written so an agent can
tell, just from reading them, which tool to reach for:

    lookup_record(record_id)  -> fetch one known record BY ITS ID.
    verify_record(record)     -> check whether an ARBITRARY record is well-formed.

Built with the official MCP Python SDK's FastMCP helper.  `pip install mcp`

DESIGN NOTE
-----------
The real logic lives in plain module-level functions (`_lookup`, `_verify`).
The MCP tools are thin wrappers registered on top of them. That keeps the tools
trivially unit-testable (see test_server.py) WITHOUT needing a live MCP client
or transport — the smoke test just calls the underlying functions directly.
"""

from __future__ import annotations

import datetime as _dt
import re

from mcp.server.fastmcp import FastMCP

# --------------------------------------------------------------------------- #
# Synthetic data + shared validation logic (no domain meaning whatsoever)
# --------------------------------------------------------------------------- #

# A tiny in-memory "database" of generic records, keyed by id. Entirely made up.
_RECORDS: dict[str, dict] = {
    "rec-001": {
        "id": "rec-001",
        "claim": "The reading room seats 60 people.",
        "source": "https://example.org/reading-room",
        "checked_date": "2026-03-01",
    },
    "rec-002": {
        "id": "rec-002",
        "claim": "Lockers are available on the second floor.",
        "source": "https://example.org/facilities/lockers",
        "checked_date": "2026-02-14",
    },
    "rec-003": {
        "id": "rec-003",
        "claim": "The help desk is staffed until 6pm.",
        "source": "https://example.org/help-desk",
        "checked_date": "2026-01-09",
    },
}

REQUIRED_FIELDS = ("id", "claim", "source", "checked_date")
_URL_RE = re.compile(r"^https?://[^\s]+\.[^\s]+", re.IGNORECASE)


def _verify(record: dict) -> dict:
    """Pure validation: is this record well-formed? Returns a structured verdict.

    Same rules as the eval harness and the skill, kept simple and readable:
    required fields present, source is an http(s) URL, date is ISO YYYY-MM-DD.
    """
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        value = record.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            errors.append(f"missing or empty field: '{field}'")

    source = record.get("source", "")
    if not isinstance(source, str) or not _URL_RE.match(source.strip()):
        errors.append(f"'source' is not a valid http(s) URL: {source!r}")

    raw_date = record.get("checked_date", "")
    if isinstance(raw_date, str):
        try:
            _dt.date.fromisoformat(raw_date.strip())
        except ValueError:
            errors.append(f"'checked_date' is not ISO YYYY-MM-DD: {raw_date!r}")
    else:
        errors.append("'checked_date' must be a string")

    return {"ok": len(errors) == 0, "errors": errors}


def _lookup(record_id: str) -> dict:
    """Pure lookup: fetch one record by id, or a structured 'not found' result."""
    record = _RECORDS.get(record_id)
    if record is None:
        return {"found": False, "id": record_id, "record": None}
    # Return a copy so callers can't mutate our in-memory store by accident.
    return {"found": True, "id": record_id, "record": dict(record)}


# --------------------------------------------------------------------------- #
# The MCP server + its tools
# --------------------------------------------------------------------------- #

mcp = FastMCP("synthetic-records")


@mcp.tool()
def lookup_record(record_id: str) -> dict:
    """Fetch a single known record from the synthetic dataset by its id.

    Use this when you already have a record's id (e.g. "rec-001") and want to
    retrieve the stored record itself. This does NOT validate or judge anything;
    it only looks up data. If the id is unknown, `found` will be false.

    Args:
        record_id: the id of the record to fetch, e.g. "rec-001".

    Returns:
        {"found": bool, "id": str, "record": {...} | None}
    """
    return _lookup(record_id)


@mcp.tool()
def verify_record(record: dict) -> dict:
    """Check whether an arbitrary record is well-formed (schema/URL/date).

    Use this when you HAVE a record (that you built, received, or fetched) and
    need to know if it is valid before trusting it — all required fields
    present, `source` a real http(s) URL, `checked_date` a valid ISO date. This
    does NOT fetch anything; it validates the record you pass in.

    Args:
        record: a record object with keys id, claim, source, checked_date.

    Returns:
        {"ok": bool, "errors": [str, ...]}   # errors is empty when ok is true
    """
    return _verify(record)


if __name__ == "__main__":
    # Run the server over stdio — the transport Claude Desktop and most local
    # MCP clients use. The client launches this process and speaks MCP to it.
    mcp.run()
