# Entities, relations and queries

- Entity types declare record schema, required/optional fields, units/date/enum metadata, relation requirements, destination/template policies, projections.
- Relation types declare source/target kind+type, cardinality/uniqueness, inverse, dangling policy. Cross-dataset refs are forbidden.
- Queries are allowlisted declarative JSON AST (no Python/SQL/eval/import/shell/network).
- Aggregates return metric definition, units, formula, timezone/date policy, incoming IDs/paths/pointers, completeness status. Unknown metric/unit → abstain/clarify, never guess.
