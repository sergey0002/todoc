# todoc

Portable typed knowledge substrate: source-native validator + bounded search/read CLI.

Files are the source of truth; indexes/cache are derived and rebuildable.
CLI-first, agent-first; web UI later as a separate adapter.

## Install

```bash
pip install -e .          # editable (dev)
# or
pip install .             # wheel
```

## Quick start

```bash
todoc init --root ./knowledge
todoc --root ./knowledge check
todoc --root ./knowledge docs search --query "refresh token" --output json
todoc --root ./knowledge docs read --id doc:notes/design.md --section "Decision" --output json
todoc --root ./knowledge records list --type workout --output json
```

## Tests

```bash
python -m pytest tests -q
python -m coverage run -m pytest tests -q
python -m coverage report
```

## Docs

- `plan/constitution.md` — normative constitution (what to build).
- `plan/implementation-plan.md` — step-by-step implementation plan (how to build).
- `SKILL.md` — parent Skill for agents.
