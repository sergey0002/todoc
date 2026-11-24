---
id: doc:ref-type-system
title: Reference: type system (generated)
doc_type: reference
lang: en
source: references/type-system.generated.md
copied: true
---

# Type system (generated)

Generated from the CLI contract (not from any specific dataset).
Run `todoc --root <PATH> types guide` for a per-dataset reference.

## dir_type / doc_type / entity_type / relation_type

- `format` ≠ `doc_type` ≠ `dir_type` ≠ `entity_type` ≠ `relation_type` ≠ query/view.
- Type descriptors are JSON with `schema_version`, `type_id`, `version`, `description`.
- Entity types may carry `ui` and `agent_instructions` as non-executable data.
