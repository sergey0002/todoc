---
id: doc:ref-data-roots
title: "Reference: data roots and config"
doc_type: reference
lang: en
source: references/data-roots-and-config.md
copied: true
created: 2026-11-26
updated: 2026-11-26
tags: [references, reference, config, roots]
---

# Data roots and config

- DATA_ROOT holds `.todoc/` (dataset/rules/types/schemas/templates/queries/identities/index/cache/generated).
- All configs are JSON with `schema_version`. Paths are root-relative; `dataset_id` survives moves.
- `todoc init --root <PATH>` creates control files only; it never scans/moves user data.
- Folder-local `<folder>/.todoc.json` holds declarative overrides (no code/shell/import/URL).
- `.todoc/` and `.todoc.json` are never indexed as content.