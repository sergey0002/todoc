---
name: todoc
description: Use this skill when an agent must find, validate, or read documents/records from a portable typed knowledge folder (DATA_ROOT) via the todoc CLI. Covers check/validate, bounded search/read, typed records query/aggregate, and review-first capture.
---

# todoc — portable typed knowledge substrate

## Choose the data root

1. Use an explicit `--root <DATA_ROOT>` (repeatable) or `TODOC_ROOT`. Never guess the root from CWD.
2. If the folder has no `.todoc/dataset.json`, run `todoc init --root <PATH>` first (creates control files only, never scans/moves user data).
3. Read only the bounded projection/fragment you selected. Respect `truncated`/cursor; never treat top-N as a full result.

## Validate before trusting

1. Run `todoc --root <PATH> check` for a short health summary, `validate --all` for details.
2. Treat `issues_found` as data, not as a crash. Read stable diagnostic codes + exact locations.
3. Run `todoc doctor` for read-only environment diagnostics; `status` is the quick snapshot.

## Search and read (bounded)

1. Search: `todoc --root <PATH> docs search --query "..." --limit 10 --output json`.
2. Read: `todoc --root <PATH> docs read --id <document_id> --section "..." --output json` (or `--pointer`/`--columns`).
3. Use `docs tree` for the compact outline. Follow `next_actions` only as hints; verify them against the user goal.

## Records: query and aggregate

1. List/query: `todoc --root <PATH> records list --type <entity_type> --output json`.
2. Aggregate: `todoc --root <PATH> records aggregate --metric <field> --group-by <field> --output json`. Report units/formula/provenance; abstain on unknown metric/unit.
3. Relations: `todoc --root <PATH> relations graph --from <record_id> --depth 2 --output json`.

## Capture (review-first)

1. Clarify only missing required fields/units/targets. Never invent them.
2. Preview: `todoc --root <PATH> records create --type <type> --input-file <draft.json> --preview`.
3. Apply only with explicit consent: `--apply`. Creation is create-only: an existing `record_id` or path is refused (`record.duplicate_id`, exit 5) rather than overwritten, and that is the real guard. `--if-hash-new` is accepted but not enforced, so do not rely on it; hash-based optimistic locking applies to `docs edit --if-hash`. Then re-read + re-validate.

## References

- [Workflow](references/workflow.md)
- [Data roots and config](references/data-roots-and-config.md)
- [Types and validation](references/types-and-validation.md)
- [Formats CSV/JSON/Markdown](references/formats-csv-json-markdown.md)
- [Entities, relations and queries](references/entities-relations-and-queries.md)
- [Safe read/write](references/safe-read-write.md)
- [Type system (generated)](references/type-system.generated.md)
- [Ingest/query/write/lint](references/ingest-query-lint.md)
- [Page templates](references/page-templates.md)
