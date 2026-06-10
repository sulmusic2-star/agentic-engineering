# `skill/` — an authored Agent Skill

This directory is one **Agent Skill**: a self-contained folder that teaches an
agent how to do a specific job well. The skill here is generic and synthetic —
`validate-a-structured-record` — and carries **zero domain data**.

```
skill/
├── SKILL.md                  # the skill: YAML frontmatter + a 3-level playbook
├── scripts/
│   └── validate_record.py    # the bundled deterministic tool the skill calls
└── README.md                 # you are here
```

## What is an Agent Skill?

A Skill is a **playbook on disk** that an agent can discover and follow. At
minimum it is a `SKILL.md` file with:

- **YAML frontmatter** — a `name` and a `description`. The description is the
  important part: it is how the agent *decides whether to use the skill at all*,
  so it states plainly what the skill does and when to reach for it.
- **A body** of instructions, optionally bundling supporting files (scripts,
  templates, references) the skill can use.

The agent reads the description, decides the skill is relevant, then follows the
instructions — pulling in the bundled files only as needed.

## "MCPs are verbs, Skills are playbooks"

A useful way to keep the two straight:

- An **MCP server** (see [`../mcp/`](../mcp/)) gives an agent **verbs** — typed,
  callable actions it otherwise could not perform (`lookup_record`,
  `verify_record`). It expands *what the agent can do*.
- A **Skill** gives an agent a **playbook** — the know-how for *how to do a
  particular job well*: which steps, in what order, with what judgement, and
  which tool to call for the parts that must be exact. It expands *how well the
  agent does it*.

In short: an MCP tool is a capability; a Skill is the procedure that uses
capabilities (including plain code and MCP tools) to get a job done right. This
skill is a playbook that, at its critical step, shells out to a bundled script.

## Why progressive disclosure matters

`SKILL.md` is deliberately written in **three levels**, disclosed on demand:

1. **Overview** — just enough for the agent to answer "is this the right skill?"
2. **Instructions** — the step-by-step, read once the skill is chosen.
3. **Reference** — a pointer to the bundled script, loaded only when it is time
   to run the exact checks.

Why bother? An agent's context window is finite and precious. Dumping every
detail up front wastes tokens, buries the signal, and makes the agent more
likely to wander. Layering the information — a short hook, then depth, then the
deterministic tool — keeps the agent focused and the context lean, while still
making the full detail available the moment it is needed.

## The deterministic-reliability point

The skill does **not** ask the model to eyeball a date or a URL and judge it.
Those checks are handed to [`scripts/validate_record.py`](scripts/validate_record.py),
a pure function that returns the same verdict every time, offline. Models are
great at the fuzzy, judgement-heavy parts of a playbook; for "is this a valid
ISO date?" you want code that is right 100% of the time. Pairing a natural-
language playbook with a small, trustworthy script is the pattern.

## Try the bundled script

```bash
# from this directory:
python scripts/validate_record.py --demo                       # valid example -> exit 0
echo '{"id":"x","claim":"","source":"nope","checked_date":"bad"}' \
  | python scripts/validate_record.py                          # invalid -> exit 1
```

No dependencies beyond the Python standard library.
