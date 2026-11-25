---
id: doc:ref-workflow
title: "Reference: workflow"
doc_type: reference
lang: en
source: references/workflow.md
copied: true
---

# Workflow

1. Choose `--root` (repeatable) or `TODOC_ROOT`. Never guess from CWD.
2. `check` (summary) → `validate --all` (details) → `search` → `read` (bounded).
3. Records: `list`/`query` → `aggregate` (units/formula/provenance) → `read`.
4. Capture: clarify missing required fields → `records create --preview` → `--apply` with consent → re-read + re-validate.
5. Fixes: `fix --diagnostic <id> --preview` → `--apply` with `--if-hash` only for verified rules.
