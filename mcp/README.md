# `mcp/` — a tiny MCP server

A minimal **Model Context Protocol (MCP)** server, built on the official MCP
Python SDK (FastMCP). It exposes two clearly-bounded, typed tools over a small
**synthetic** dataset of generic "claim" records. No real data, no API keys.

```
mcp/
├── server.py        # the MCP server: two tools over synthetic records
├── test_server.py   # smoke test — calls the tools directly (no live client)
└── README.md        # you are here
```

## What is MCP?

MCP is an open protocol that standardizes how an AI application connects to
external context and capabilities. It is a **client–server** model:

- The **client** lives inside the AI app (e.g. Claude Desktop, or an SDK-based
  agent). It speaks MCP on the model's behalf.
- A **server** (like this one) exposes capabilities the client can use.

A server can offer **three primitives**:

| Primitive | What it is | Who drives it |
|---|---|---|
| **Tools** | Actions the agent can **call** (typed functions) | model-controlled |
| **Resources** | Read-only data the agent can **fetch** (files, URLs, records) | app-controlled |
| **Prompts** | Reusable **prompt templates** the agent can invoke | user-controlled |

Think of it as a universal adapter: write the capability once as an MCP server,
and any MCP-compatible client can use it. This server demonstrates the **tools**
primitive.

## The two tools (and why an agent can tell them apart)

The tool descriptions are written so an agent can pick the right one from the
docstring alone:

- **`lookup_record(record_id: str)`** — *fetch* one known record by its id (e.g.
  `"rec-001"`). Pure data retrieval; it does not judge anything. Returns
  `{"found": bool, "id": str, "record": {...} | None}`.
- **`verify_record(record: dict)`** — *validate* an arbitrary record you already
  have (all fields present, `source` a real URL, `checked_date` a valid ISO
  date). It does not fetch anything. Returns `{"ok": bool, "errors": [...]}`.

The split is deliberate: one tool is "go get data," the other is "judge the data
I have." Clear, non-overlapping verbs are what let an agent choose correctly
without guessing.

## Install & run

```bash
pip install mcp          # the official MCP Python SDK (provides FastMCP)
python server.py         # starts the server over stdio (Ctrl-C to stop)
```

`server.py` runs over **stdio**, the transport local clients use: the client
launches the server as a subprocess and exchanges MCP messages over its standard
in/out.

## How a client connects

**Claude Desktop** (or any compatible client) is pointed at the server via its
MCP config, e.g.:

```jsonc
{
  "mcpServers": {
    "synthetic-records": {
      "command": "python",
      "args": ["/absolute/path/to/mcp/server.py"]
    }
  }
}
```

On launch the client starts the process, lists the available tools, and the
model can then call `lookup_record` / `verify_record` as needed. An **SDK
client** connects the same way programmatically (open a stdio session to the
server, list tools, call them).

## The smoke test

`test_server.py` does **not** require a live MCP client. It imports `server.py`
and:

- calls `lookup_record` / `verify_record` directly on synthetic input and
  asserts the results are correct, and
- asserts both tools are actually registered with FastMCP and expose an input
  schema + description (so a real agent could discover and call them).

```bash
# from this directory:
python -m pytest        # 7 tests
```

Only dependency: `mcp` (plus `pytest` to run the test).
