"""
test_server.py — a smoke test for the MCP server.

We do NOT spin up a live MCP client or transport here. That would be slow and
flaky for a smoke test. Instead we import the server module and exercise the
tool functions directly on synthetic input — proving the tools return correct
results — plus one check that the tools are actually registered with FastMCP and
expose a usable schema (so an agent could discover them).

Run from this directory:
    python -m pytest
"""

from __future__ import annotations

import asyncio

import server


# --------------------------------------------------------------------------- #
# lookup_record
# --------------------------------------------------------------------------- #

def test_lookup_known_record():
    result = server.lookup_record("rec-001")
    assert result["found"] is True
    assert result["record"]["id"] == "rec-001"
    assert result["record"]["claim"]  # non-empty


def test_lookup_unknown_record():
    result = server.lookup_record("does-not-exist")
    assert result["found"] is False
    assert result["record"] is None


def test_lookup_returns_a_copy_not_the_live_store():
    # Mutating the returned record must not corrupt the in-memory dataset.
    result = server.lookup_record("rec-002")
    result["record"]["claim"] = "MUTATED"
    fresh = server.lookup_record("rec-002")
    assert fresh["record"]["claim"] != "MUTATED"


# --------------------------------------------------------------------------- #
# verify_record
# --------------------------------------------------------------------------- #

def test_verify_valid_record():
    record = {
        "id": "rec-x",
        "claim": "A plain factual statement.",
        "source": "https://example.org/a",
        "checked_date": "2026-01-01",
    }
    result = server.verify_record(record)
    assert result["ok"] is True
    assert result["errors"] == []


def test_verify_catches_missing_source_bad_url_and_bad_date():
    bad = {
        "id": "rec-y",
        "claim": "",                 # empty claim
        "source": "not-a-url",       # invalid URL
        "checked_date": "01-2026",   # not ISO
    }
    result = server.verify_record(bad)
    assert result["ok"] is False
    # All three distinct problems should be reported.
    joined = " ".join(result["errors"])
    assert "claim" in joined
    assert "source" in joined
    assert "checked_date" in joined


def test_verify_of_a_looked_up_record_is_valid():
    # The two tools compose: a record fetched by lookup should verify cleanly.
    fetched = server.lookup_record("rec-003")
    result = server.verify_record(fetched["record"])
    assert result["ok"] is True


# --------------------------------------------------------------------------- #
# The tools are actually registered with FastMCP (agent-discoverable)
# --------------------------------------------------------------------------- #

def test_tools_are_registered_with_schemas():
    # list_tools is async in the SDK; drive it with asyncio for the test.
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {"lookup_record", "verify_record"} <= names

    # Each tool should expose an input schema and a (non-empty) description so an
    # agent can tell what it does and how to call it.
    by_name = {t.name: t for t in tools}
    assert by_name["lookup_record"].description
    assert "properties" in by_name["lookup_record"].inputSchema
    assert "record_id" in by_name["lookup_record"].inputSchema["properties"]
    assert "record" in by_name["verify_record"].inputSchema["properties"]
