---
id: doc:ref-types-validation
title: "Reference: types and validation"
doc_type: reference
lang: en
source: references/types-and-validation.md
copied: true
created: 2026-11-26
updated: 2026-11-26
tags: [references, reference, validation, types]
---

# Types and validation

- `format` ≠ `doc_type` ≠ `dir_type` ≠ `entity_type` ≠ `relation_type` ≠ query/view.
- Resolution: explicit declaration → nearest local config → dataset rules (exact path → basename → glob) → reserved defaults → unknown. Ties with different assignments are diagnostics, not silent winners.
- Reserved basenames: `.research`, `architecture`, `constitution`, `harness`, `glossary`, `plan` (as `**/plan/`). Canonical `harness`; `harnes` only via alias.
- Diagnostics carry stable codes, severity, exact locations (CSV row+column, JSON Pointer, Markdown line+anchor) and optional `suggested_fixes` with rationale/evidence.