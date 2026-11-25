"""Safe declarative records query/aggregate (E7). No eval/SQL/shell."""

from __future__ import annotations

from typing import Any

from todoc.application import temporal
from todoc.errors import ValidationError


def _get_field(data: dict[str, Any], field_path: str) -> Any:
    current: Any = data
    for part in field_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _matches(data: dict[str, Any], filters: dict[str, Any]) -> bool:
    for field_path, expected in filters.items():
        actual = _get_field(data, field_path)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif isinstance(expected, dict) and ("$gte" in expected or "$lte" in expected):
            if "$gte" in expected and not (actual is not None and actual >= expected["$gte"]):
                return False
            if "$lte" in expected and not (actual is not None and actual <= expected["$lte"]):
                return False
        elif actual != expected:
            return False
    return True


def query_records(records: list[dict[str, Any]], entity_type: str | None = None,
                  filters: dict[str, Any] | None = None, limit: int = 200,
                  as_of: str | None = None) -> tuple[list[dict[str, Any]], int, bool]:
    """``as_of`` срезает выборку по времени правды: остаются записи, для которых
    ``valid_from <= T < valid_to`` и которые ещё не закрыты ``superseded_at``.
    Записи без темпоральных полей видны всегда — обратная совместимость (§10).
    """
    selected = temporal.records_as_of(records, as_of)
    selected = [r for r in selected if entity_type is None or r.get("entity_type") == entity_type]
    if filters:
        selected = [r for r in selected if _matches(r.get("data") or {}, filters)]
    selected.sort(key=lambda r: str(r.get("record_id", "")))
    total = len(selected)
    return selected[:limit], total, total > limit


def aggregate_records(records: list[dict[str, Any]], entity_type: str, metric_field: str,
                      group_by: str | None = None,
                      metric_spec: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sum a numeric field, optionally grouped. Returns units/provenance.

    Units are checked **per group**: aggregating metrics measured in ``count``,
    ``ratio`` and ``ms`` is legitimate when they are grouped apart, while mixing
    two units inside one group is the error worth refusing. The previous global
    check made any heterogeneous metric set unaggregatable, even with --group-by.

    ``metric_spec`` is the ``metric_fields.<field>`` entry of the entity type, when
    the type declares one. It carries a natural-language ``prompt`` and a ``unit``;
    nothing in it is evaluated. The core aggregates by summing this one field, and
    says so in ``aggregation`` — a derived metric (``reps × weight_kg``) is a stored
    field or the caller's arithmetic, not something this function will invent.
    """
    selected = [r for r in records if r.get("entity_type") == entity_type]
    if not selected:
        raise ValidationError(f"No records of type {entity_type!r}", "query.no_records")
    spec = metric_spec if isinstance(metric_spec, dict) else {}
    groups: dict[str, float] = {}
    group_units: dict[str, str] = {}
    incoming: list[str] = []
    for record in selected:
        value = _get_field(record.get("data") or {}, metric_field)
        unit = ""
        if isinstance(value, dict) and "value" in value:
            unit = str(value.get("unit", ""))
            number = float(value["value"])
        elif isinstance(value, (int, float)):
            number = float(value)
        else:
            raise ValidationError(f"Metric field {metric_field!r} is not numeric in {record.get('record_id')}",
                                  "query.unknown_metric")
        key = "all"
        if group_by:
            grouped = _get_field(record.get("data") or {}, group_by)
            key = str(grouped) if grouped is not None else "unknown"
        known = group_units.get(key)
        if known is None:
            group_units[key] = unit
        elif known != unit:
            raise ValidationError(f"Unit mismatch in aggregate: group {key!r} mixes {known!r} and {unit!r}",
                                  "query.unit_mismatch")
        groups[key] = groups.get(key, 0.0) + number
        incoming.append(str(record.get("record_id", "")))
    distinct = sorted(set(group_units.values()))
    return {
        "entity_type": entity_type,
        "metric": metric_field,
        "units": distinct[0] if len(distinct) == 1 else "",
        "group_units": group_units,
        # FR-8.2 требует формулу в ответе. Здесь она честная: описывает то, что ядро
        # действительно сделало (сумма одного поля), а не то, что кто-то объявил.
        # Объявляется в типе не формула, а `prompt` — вычисляемых выражений нет (P1-11).
        "formula": f"sum({metric_field})",
        "prompt": str(spec.get("prompt", "")),
        "groups": groups,
        "incoming_ids": sorted(incoming),
        "completeness": "complete",
    }


def graph_neighbors(relations: list[dict[str, Any]], from_id: str, type_id: str | None = None,
                    depth: int = 1, limit: int = 100) -> list[dict[str, Any]]:
    """BFS over typed edges up to depth, bounded by limit."""
    visited = {from_id}
    frontier = [from_id]
    result: list[dict[str, Any]] = []
    for _ in range(depth):
        next_frontier: list[str] = []
        for node in frontier:
            for rel in relations:
                if type_id is not None and rel.get("type_id") != type_id:
                    continue
                neighbor = None
                if rel.get("source_id") == node:
                    neighbor = rel.get("target_id")
                elif rel.get("target_id") == node:
                    neighbor = rel.get("source_id")
                if neighbor and neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.append(str(neighbor))
                    result.append({"type_id": rel.get("type_id"), "from": node, "to": neighbor})
                    if len(result) >= limit:
                        return result
        frontier = next_frontier
        if not frontier:
            break
    return result
