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
                    depth: int = 1, limit: int = 100,
                    mentions: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """BFS over typed edges up to depth, bounded by limit.

    ``mentions`` (план entity-catalog З2/T6): md-упоминания цели добавляются
    рёбрами ``via: "mention"`` у корня — вершины-md в обход BFS не вовлекаются.
    """
    visited = {from_id}
    frontier = [from_id]
    result: list[dict[str, Any]] = []
    for m in mentions or []:
        if type_id not in (None, "mention"):
            continue
        if m.get("target") == from_id and m.get("source_file") not in visited:
            visited.add(str(m.get("source_file")))
            result.append({"type_id": "mention", "via": "mention", "from": from_id,
                           "to": m.get("source_file"), "fragment": m.get("source_fragment", "")})
        elif m.get("source_file") == from_id and m.get("target") not in visited:
            visited.add(str(m.get("target")))
            result.append({"type_id": "mention", "via": "mention", "from": from_id,
                           "to": m.get("target"), "fragment": m.get("source_fragment", "")})
        if len(result) >= limit:
            return result
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


def build_tree(relations: list[dict[str, Any]], from_id: str, type_id: str | None = None,
               depth: int = 1, limit: int = 100,
               mentions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Вложенное дерево связей (план entity-catalog З3/T11).

    Те же данные, что у graph (relations + mentions): рёбра каждой вершины
    группируются по type_id, направление помечено ("out"/"in"), mention-рёбра
    несут via "mention". Вершины не разворачиваются повторно (cycle).
    """
    visited = {from_id}
    counter = {"n": 0}

    def expand(node: str, level: int) -> list[dict[str, Any]]:
        if level > depth or counter["n"] >= limit:
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
                    raw.append(("mention", "out", str(m.get("source_file")), str(m.get("source_fragment", ""))))
                elif m.get("source_file") == node:
                    raw.append(("mention", "out", str(m.get("target")), str(m.get("source_fragment", ""))))
        groups: dict[str, list[dict[str, Any]]] = {}
        for type_, direction, other, fragment in raw:
            groups.setdefault(type_, []).append({"direction": direction, "id": other, "fragment": fragment})
        result: list[dict[str, Any]] = []
        for type_ in sorted(groups):
            edges: list[dict[str, Any]] = []
            for item in groups[type_]:
                if counter["n"] >= limit:
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

    return {"root": from_id, "groups": expand(from_id, 1), "truncated": counter["n"] >= limit}
