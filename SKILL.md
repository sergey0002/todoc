---
name: todoc
description: Use this skill when an agent must find, validate, or read documents/records from a portable typed knowledge folder (DATA_ROOT) via the todoc CLI. Covers check/validate, bounded search/read, typed records query/aggregate, and review-first capture.
---

# todoc — portable typed knowledge substrate

## Choose the data root

1. Use an explicit `--root <DATA_ROOT>` (repeatable) or `TODOC_ROOT`. Never guess the root from CWD.
2. If the folder has no `.todoc/dataset.json`, run `todoc init --apply --root <PATH>` first (creates control files only, never scans/moves user data).
3. Read only the bounded projection/fragment you selected. Respect `truncated`/cursor; never treat top-N as a full result.

## Validate before trusting

1. Run `todoc --root <PATH> check` for a short health summary, `validate --all` for details.
2. Treat `issues_found` as data, not as a crash. Read stable diagnostic codes + exact locations.
3. Run `todoc doctor` for read-only environment diagnostics; `status` is the quick snapshot.

## Search and read (bounded)

For an inventory by document type or lifecycle status, start with metadata:
`todoc docs list --root <PATH> --type idea --fields id,path,title,status --limit 100`.
Read `data.result.items` and check `data.meta.complete` and `next_cursor`.
Use one successful probe before repeating a command across many inputs.

1. Search: `todoc --root <PATH> docs search --query "..." --limit 10 --output json`.
2. Read: `todoc --root <PATH> docs read --id <document_id> --section "..." --output json` (or `--pointer`/`--columns`).
3. Use `docs tree` for the compact outline. Follow `next_actions` only as hints; verify them against the user goal.

## Skills routing

Before any non-trivial task run `todoc skills tree --root <PATH>`; pick a skill by its description (section = domain), read its body with `todoc skills read --root <PATH> --path <path from the tree>`, and follow that SKILL.md (references/ and scripts/ as needed). If nothing matches, work without a skill; never modify third-party skills. The skills vault itself is never mounted into platform skill directories — only the `todoc` dispatcher skill is (`todoc skills attach --apply --to <platform skills dir> --root <PATH>`).

## Records: query and aggregate

1. List/query: `todoc --root <PATH> records list --type <entity_type> --output json`.
2. Aggregate: `todoc --root <PATH> records aggregate --metric <field> --group-by <field> --output json`. Report units/formula/provenance; abstain on unknown metric/unit.
3. Relations: `todoc --root <PATH> relations graph --from <record_id> --depth 2 --output json`.

## Capture (review-first)

1. Clarify only missing required fields/units/targets. Never invent them.
2. Create new items via CLI templates: `todoc --root <PATH> docs new --apply --type <type> --title "..." --path <dir>/<slug>.md` or `todoc --root <PATH> records create --type <type> --input-file <draft.json> --preview` → `--apply` (create-only: an existing `record_id` or path is refused with `record.duplicate_id`, exit 5).
3. **Edit existing `.md`, `.json`, and `.csv` files directly** with your native editor tool (never hand-edit `created`/`updated` or generated views with `"generated": true`), then **immediately run `todoc sync --apply --root <PATH> <file_path>`** (optionally `--if-hash <hash>`) to bump `updated`, record history ranges, refresh the index, and validate (`ok: true`, `diagnostics: []`).

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

## Safe document moves

Use `todoc docs move --root <PATH> --from <old.md> --to <new.md>` instead of a manual rename. Inspect preview and apply with `--apply --if-plan-hash <plan_hash>`; a modified corpus needs a fresh preview. `--keep-id` preserves identity; `--pin-type` fixes the inferred type. Move already finalizes its files: do not run a second sync. To undo, preview `todoc revert --root <PATH> --change <change_id>`, then apply with its own hash. Never repeat an apply blindly after exit 6: `committed=true` means sources were saved; rebuild the index. v1 rejects affected unsupported link forms, existing validation errors, active deltas and SKILL.md moves. Multi-file rollback is not crash-atomic.
