---
name: validate-a-structured-record
description: >-
  Normalize and validate a small structured "claim" record (id, claim, source,
  checked_date) before it is stored or shown. Use this whenever you have a
  record that asserts something and cites a source, and you need to confirm it
  is well-formed — all fields present, the source a real URL, the date a valid
  ISO date — before trusting it. Delegates the exact checks to a bundled,
  deterministic script.
---

# Validate a structured record

<!--
This skill is written with PROGRESSIVE DISCLOSURE — three levels.
An agent reads only as far as it needs:

  Level 1  the description (in the YAML above) + the overview below.
           Just enough to decide "is this the right skill for the task?"
  Level 2  the step-by-step instructions, read once the skill is chosen.
  Level 3  the bundled script under scripts/, run for the part that must be
           exact every time. The agent does not need to read the script's
           internals — only how to call it and how to read its output.

Loading the whole world into context up front is wasteful and error-prone.
Disclosing it in layers keeps the agent focused and the context window small.
-->

## Level 1 — Overview (what this is, when to use it)

Use this skill when you are handed a **structured record that makes a claim and
cites a source**, and it must be well-formed before you trust, store, or display
it. A record looks like:

```json
{
  "id": "rec-42",
  "claim": "The reading room seats 60 people.",
  "source": "https://example.org/reading-room",
  "checked_date": "2026-03-01"
}
```

"Well-formed" means: every required field is present and non-empty, `source` is
a real `http(s)` URL, and `checked_date` is a valid ISO date (`YYYY-MM-DD`).

> The actual checks are **not** done by reasoning — they are delegated to a
> bundled script (Level 3) so they are exact and identical every time. Your job
> as the agent is to gather the record, run the script, and act on its verdict.

## Level 2 — Instructions (how to run it)

1. **Assemble the record** as a single JSON object with the four fields above.
   If you only have loose pieces, normalize them first:
   - Trim surrounding whitespace from every value.
   - Convert the date to ISO `YYYY-MM-DD` if you can do so *unambiguously*. If a
     date is ambiguous (e.g. `01/02/2026` — is that Jan 2 or Feb 1?), do **not**
     guess; leave it as-is and let the validator reject it.
   - Do not invent a `source`. A missing source must stay missing so it fails.

2. **Run the bundled validator** (Level 3). Pass the record on stdin:

   ```bash
   echo '{"id":"rec-42","claim":"...","source":"https://...","checked_date":"2026-03-01"}' \
     | python scripts/validate_record.py
   ```

   or from a file: `python scripts/validate_record.py path/to/record.json`.

3. **Branch on the result.** The script prints JSON and sets an exit code:
   - **exit 0** (`"ok": true`) — the record is valid. Proceed to store/use it.
   - **exit 1** (`"ok": false`) — invalid. Read the `errors` array, report each
     problem to the user in plain language, and (if you can) fix and re-run.
     Never pass an invalid record downstream.
   - **exit 2** — the *input* was unusable (bad JSON, nothing piped in). Fix how
     you are calling the script; this is not a verdict about the record.

4. **Report.** Summarize for the user: the `id`, whether it passed, and — if it
   failed — the specific errors. Do not paraphrase a "fail" into a "pass."

## Level 3 — Reference: the bundled deterministic script

The exact validation lives in [`scripts/validate_record.py`](scripts/validate_record.py).

- It is a **pure, deterministic** validator: same input → same verdict, every
  time, with no network and no model call. That reliability is the entire reason
  the skill offloads the checks to code instead of asking the model to "look at
  the date and decide."
- You do **not** need to read its internals to use it — only the contract:
  - **Input:** one JSON record (stdin, a file path, or `--demo` for a built-in
    valid example).
  - **Output:** JSON `{"ok": bool, "id": ..., "errors": [...]}` on stdout.
  - **Exit codes:** `0` valid, `1` invalid, `2` bad input.
- Quick self-check that the tool works at all:

  ```bash
  python scripts/validate_record.py --demo   # prints "ok": true, exits 0
  ```

That is the whole skill: a short playbook (this file) wrapped around a small,
trustworthy tool (the script).
