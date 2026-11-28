"""Safe declarative records query/aggregate (E7). No eval/SQL/shell."""

from __future__ import annotations

import math
from collections import defaultdict, deque
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
    group_incoming: dict[str, list[str]] = {}
    for record in selected:
        value = _get_field(record.get("data") or {}, metric_field)
        unit = ""
        if isinstance(value, dict) and "value" in value:
            unit = str(value.get("unit", ""))
            value = value["value"]
        try:
            if type(value) not in (int, float):
                raise TypeError
            number = float(value)
            if not math.isfinite(number):
                raise ValueError
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError(f"Metric field {metric_field!r} is not a finite number in {record.get('record_id')}",
                                  "query.unknown_metric") from exc
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
        total = groups.get(key, 0.0) + number
        if not math.isfinite(total):
            raise ValidationError(f"Aggregate exceeds the numeric range in group {key!r}", "query.aggregate_overflow")
        groups[key] = total
        record_id = str(record.get("record_id", ""))
        incoming.append(record_id)
        group_incoming.setdefault(key, []).append(record_id)
    distinct = sorted(set(group_units.values()))
    return {
        "entity_type": entity_type,
        "metric": metric_field,
        "units": distinct[0] if len(distinct) == 1 else "",
        "group_units": group_units,
        "group_incoming_ids": {key: sorted(ids) for key, ids in group_incoming.items()},
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
                    depth: int = 1, limit: int | None = 100,
                    mentions: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Traverse incident edges by distance and keep their original direction and occurrence."""
    edges = []
    for relation in relations:
        edge = {"type_id": relation["type_id"], "from": relation["source_id"], "to": relation["target_id"]}
        if "source_path" in relation:
            edge["provenance"] = {"path": relation["source_path"], "pointer": relation["source_pointer"]}
        edges.append(edge)
    for mention in mentions or []:
        edge = {"type_id": "mention", "via": "mention", "from": mention["source_file"],
                "to": mention["target"], "fragment": mention.get("source_fragment", ""),
                "provenance": {"path": mention["source_file"], "line": mention.get("source_line")}}
        edges.append(edge)
    adjacent: dict[str, list[tuple[int, dict[str, Any], str]]] = defaultdict(list)
    for position, edge in enumerate(edges):
        if type_id is not None and edge["type_id"] != type_id:
            continue
        source, target = edge["from"], edge["to"]
        adjacent[source].append((position, edge, target))
        if source != target:
            adjacent[target].append((position, edge, source))
    queue = deque([(from_id, 0)])
    visited_nodes = {from_id}
    visited_edges = set()
    result = []
    while queue:
        node, distance = queue.popleft()
        if distance >= depth:
            continue
        for occurrence, edge, other in adjacent[node]:
            if occurrence not in visited_edges:
                if limit is not None and len(result) >= limit:
                    return result
                visited_edges.add(occurrence)
                result.append(edge)
            if other not in visited_nodes:
                visited_nodes.add(other)
                queue.append((other, distance + 1))
    return result


def build_tree(relations: list[dict[str, Any]], from_id: str, type_id: str | None = None,
               depth: int = 1, limit: int | None = 100,
               mentions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Вложенное дерево связей (план entity-catalog З3/T11).

    Те же данные, что у graph (relations + mentions): рёбра каждой вершины
    группируются по type_id, направление помечено ("out"/"in"), mention-рёбра
    несут via "mention". Вершины не разворачиваются повторно (cycle).
    """
    visited = {from_id}
    counter = {"n": 0, "truncated": False}

    def expand(node: str, level: int) -> list[dict[str, Any]]:
        if level > depth or counter["truncated"]:
            return []
        raw: list[tuple[str, str, str, str]] = []  # (type_id, direction, id, fragment)
        for rel in relations:
            if type_id is not None and rel.get("type_id") != type_id:
                continue
            if rel.get("source_id") == node:
                raw.append((str(rel.get("type_id")), "out", str(rel.get("target_id")), ""))
            elif rel.get("target_id") == node:
                raw.append((str(rel.get("type_id")), "in", str(rel.get("source_id")), ""))
        if type_id in (None, "mention"):
            for m in mentions or []:
                if m.get("target") == node:
                    raw.append(("mention", "in", str(m.get("source_file")), str(m.get("source_fragment", ""))))
                elif m.get("source_file") == node:
                    raw.append(("mention", "out", str(m.get("target")), str(m.get("source_fragment", ""))))
        groups: dict[str, list[dict[str, Any]]] = {}
        for type_, direction, other, fragment in raw:
            groups.setdefault(type_, []).append({"direction": direction, "id": other, "fragment": fragment})
        result: list[dict[str, Any]] = []
        for type_ in sorted(groups):
            edges: list[dict[str, Any]] = []
            for item in groups[type_]:
                if limit is not None and counter["n"] >= limit:
                    counter["truncated"] = True
                    return result + [{"type_id": type_, "edges": edges, "truncated": True}] if edges else result
                counter["n"] += 1
                edge: dict[str, Any] = {"direction": item["direction"], "id": item["id"]}
                if type_ == "mention":
                    edge["via"] = "mention"
                    if item["fragment"]:
                        edge["fragment"] = item["fragment"]
                if item["id"] in visited:
                    edge["cycle"] = True
                else:
                    visited.add(item["id"])
                    if level < depth:
                        edge["children"] = expand(item["id"], level + 1)
                edges.append(edge)
            result.append({"type_id": type_, "edges": edges})
        return result

    return {"root": from_id, "groups": expand(from_id, 1), "truncated": counter["truncated"]}


def slice_relation_tree(tree: dict[str, Any], start: int, end: int) -> tuple[dict[str, Any], int]:
    """Select traversal occurrences while retaining ancestor context for each page."""
    ordinal = 0

    def visit(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal ordinal
        result = []
        for group in groups:
            selected_edges = []
            lost = False
            for edge in group["edges"]:
                included = start <= ordinal < end
                ordinal += 1
                nested = visit(edge.get("children", []))
                if not included:
                    lost = True
                if included or nested:
                    row = {key: value for key, value in edge.items() if key != "children"}
                    if nested:
                        row["children"] = nested
                    if not included:
                        row["context_only"] = True
                    selected_edges.append(row)
            if selected_edges:
                item = {"type_id": group["type_id"], "edges": selected_edges}
                if lost:
                    item["truncated"] = True
                result.append(item)
        return result

    groups = visit(tree["groups"])
    return {"root": tree["root"], "groups": groups, "truncated": end < ordinal}, ordinal
