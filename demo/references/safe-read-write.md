---
id: doc:ref-safe-read-write
title: "Reference: safe read/write"
doc_type: reference
lang: en
source: references/safe-read-write.md
copied: true
created: 2026-11-26
updated: 2026-11-26
tags: [references, reference, write, read]
---

# Safe read/write

- Existing sources are read-only. Allowed: `docs new`, `records create` (new JSON), preview/diff + `--apply` with `expected_hash`.
- Every write: temp + atomic replace/create, re-parse + schema + type + relation validation, index update. Concurrent update → conflict + re-read. Invalid record leaves the original untouched.
- Advisory/LLM suggestions never get auto-apply. Ambiguous fixes are not applied automatically.
- `next_actions` are argv-array hints, never auto-execution.