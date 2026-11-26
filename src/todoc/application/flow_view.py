"""flow_view: витрина и навигатор дерева решений флоу (план entity-catalog З8, T1/T2).

Чистая сборка markdown из записи flow: state machine, таблица решений с колонкой
«Режим», mermaid, lineage, термины по ``uses_term``. Никакого I/O — детерминизм
проверяется тестом на равенство двух сборок. ``--write`` материализует витрину
с fm ``derived_from`` (дрейф ловит существующий ``todoc stale``).
"""
from __future__ import annotations

import json
from typing import Any

MODES = {"auto", "ask-user"}
NODE_TYPES = {"question", "action", "terminal"}

_TABLE_HEADER = [
    "| # | Условие (when) | Действие / исход | Правило | Режим |",
    "|---|----------------|------------------|---------|-------|",
]


def _mode(props: dict[str, Any] | None) -> str:
    props = props or {}
    mode = props.get("mode")
    return mode if mode in MODES else "auto"


def _flow_rules(record: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Правила флоу: ребро belongs_to от правила к этому флоу."""
    flow_id = record["record_id"]
    return [rule for rule in rules
            if any(r.get("type_id") == "belongs_to" and (r.get("target") or {}).get("id") == flow_id
                   for r in (rule.get("relations") or []))]


def _rule_condition(rule: dict[str, Any]) -> str:
    examples = rule.get("examples") or []
    if examples:
        ex = examples[0]
        given = str(ex.get("given", "")).strip()
        when = str(ex.get("when", "")).strip()
        return f"{given}; {when}" if given and when else given or when or "—"
    return str(rule.get("statement", "")).strip() or "—"


def _rule_then(rule: dict[str, Any]) -> str:
    examples = rule.get("examples") or []
    if examples:
        return str(examples[0].get("then", "")).strip() or "—"
    return "—"


def _state_section(record: dict[str, Any]) -> str:
    states = record.get("states") or []
    outcomes = record.get("outcomes") or []
    lines = ["## Жизненный цикл", "", "```mermaid", "stateDiagram-v2", "[*] --> " + _sid(states[0] if states else "start")]
    for state in states:
        nxt = states[states.index(state) + 1 : 2 + states.index(state)]
        for target in nxt:
            lines.append(f"{_sid(state)} --> {_sid(target)}")
    lines.append(f"{_sid(states[-1]) if states else 'start'} --> [*]")
    lines.append("```")
    if outcomes:
        lines += ["", "Исходы: " + ", ".join(f"`{o}`" for o in outcomes)]
    return "\n".join(lines)


def _sid(state: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in state)


def _table_section(record: dict[str, Any], rules: list[dict[str, Any]]) -> str:
    tree = record.get("tree") or {}
    by_id = {n["id"]: n for n in tree.get("nodes", [])}
    rows: list[list[str]] = []
    number = 0
    for edge in tree.get("edges", []):
        target = by_id.get(edge.get("to", ""))
        if not target or target.get("type") != "terminal":
            continue
        number += 1
        source = by_id.get(edge.get("from", ""), {})
        condition = edge.get("when") or source.get("prompt") or edge.get("from", "")
        outcome = str((target.get("props") or {}).get("error_code") or target.get("prompt") or target["id"])
        rule_id = "—"
        for rule in rules:
            codes = {str(ex.get("then", "")).strip() for ex in rule.get("examples") or []}
            if outcome in codes:
                rule_id = f"`{rule['record_id']}`"
                break
        rows.append([str(number), condition, outcome, rule_id, _mode(target.get("props"))])
    if not rows:
        return ""
    lines = ["## Таблица решений", ""] + _TABLE_HEADER
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def _mermaid_section(record: dict[str, Any]) -> str:
    tree = record.get("tree") or {}
    if not tree.get("nodes"):
        return ""
    lines = ["## Диаграмма исходов", "", "```mermaid", "flowchart TD"]
    for node in tree["nodes"]:
        label = str(node.get("prompt") or node["id"]).replace('"', "'").strip()
        shape = "{{" + label + "}}" if node.get("type") == "question" else "[" + label + "]"
        lines.append(f'    {node["id"]}{shape}')
    for edge in sorted(tree.get("edges", []), key=lambda e: (e.get("from", ""), e.get("priority") or 0)):
        label = str(edge.get("when") or "").replace('"', "'").strip()
        lines.append(f'    {edge["from"]} -->|"{label}"| {edge["to"]}' if label else
                     f'    {edge["from"]} --> {edge["to"]}')
    lines.append("```")
    return "\n".join(lines)


def _lineage_section(record: dict[str, Any], rules: list[dict[str, Any]]) -> str:
    deps = [r["target"]["id"] for r in record.get("relations") or []
            if r.get("type_id") == "depends_on" and (r.get("target") or {}).get("id")]
    flow_rules = _flow_rules(record, rules)
    if not deps and not flow_rules:
        return ""
    lines = ["## Lineage"]
    if deps:
        lines += ["", "Зависимости:", *[f"- `{d}`" for d in deps]]
    if flow_rules:
        lines += ["", "Правила флоу:", *[f"- `{r['record_id']}`" for r in flow_rules]]
    return "\n".join(lines)


def _terms_section(record: dict[str, Any], terms: list[dict[str, Any]]) -> str:
    used = [r["target"]["id"] for r in record.get("relations") or []
            if r.get("type_id") == "uses_term" and (r.get("target") or {}).get("id")]
    if not used:
        return ""
    lines = ["## Термины"]
    for term_id in used:
        term = next((t for t in terms if t.get("record_id") == term_id), None)
        title = term.get("title", term_id) if term else term_id
        lines.append(f"- `{term_id}` — {title}" + (f": {term['definition']}" if term and term.get("definition") else ""))
    return "\n".join(lines)


def _bfs(edges: list[dict[str, Any]], by_id: dict[str, dict[str, Any]], start: str) -> list[dict[str, Any]]:
    """Путь по минимальному приоритету из start до terminal; защита от циклов."""
    seen: set[str] = set()
    current = start
    steps: list[dict[str, Any]] = []
    while current and current not in seen:
        seen.add(current)
        node = by_id.get(current)
        if node is None:
            break
        steps.append({"node_id": current, "type": node.get("type"),
                      "prompt": node.get("prompt"), "mode": _mode(node.get("props"))})
        if node.get("type") == "terminal":
            break
        outgoing = sorted((e for e in edges if e.get("from") == current),
                          key=lambda e: (e.get("priority") or 0, e.get("to", "")))
        current = outgoing[0]["to"] if outgoing else None
    return steps


def _all_paths(edges: list[dict[str, Any]], by_id: dict[str, dict[str, Any]], start: str) -> list[dict[str, Any]]:
    """Все ациклические пути из start до терминалов (DFS по отсортированным рёбрам)."""
    paths: list[list[dict[str, Any]]] = []
    stack: list[tuple[str, list[str], set[str]]] = [(start, [], {start})]
    while stack:
        node_id, trail, seen = stack.pop()
        node = by_id.get(node_id)
        if node is None:
            continue
        steps = trail + [{"node_id": node_id, "type": node.get("type"),
                          "prompt": node.get("prompt"), "mode": _mode(node.get("props"))}]
        if node.get("type") == "terminal":
            paths.append({"steps": steps})
            continue
        outgoing = sorted((e for e in edges if e.get("from") == node_id),
                          key=lambda e: (e.get("priority") or 0, e.get("to", "")))
        for edge in reversed(outgoing):
            nxt = edge["to"]
            if nxt in seen:
                continue
            stack.append((nxt, steps, seen | {nxt}))
    return paths


def build_flow_view(record: dict[str, Any], rules: list[dict[str, Any]] | None = None,
                    terms: list[dict[str, Any]] | None = None,
                    at: str | None = None) -> dict[str, Any]:
    """Собрать витрину флоу. ``at`` — старт обхода с узла (walk --at).

    Возвращает {id, title, actor, sections{state,table,mermaid,lineage,terms},
    markdown, walk, walk_all}. Каждый ключ sections — markdown-текст секции
    (пустая строка, если данных нет).
    """
    rules = list(rules or [])
    terms = list(terms or [])
    record_id = str(record.get("record_id", ""))
    title = str(record.get("title", record_id))
    actor = str(record.get("actor", ""))
    sections = {
        "state": _state_section(record),
        "table": _table_section(record, rules),
        "mermaid": _mermaid_section(record),
        "lineage": _lineage_section(record, rules),
        "terms": _terms_section(record, terms),
    }
    present = [k for k in ("state", "table", "mermaid", "lineage", "terms") if sections[k]]
    body = "\n\n".join(sections[k] for k in present)
    markdown = f"# {title}\n\n**Запись:** `{record_id}`" + (f" · **Актор:** {actor}" if actor else "") + "\n\n" + body
    tree = record.get("tree") or {}
    by_id = {n["id"]: n for n in tree.get("nodes", [])}
    edges = tree.get("edges") or []
    start = at or (tree.get("nodes") or [{}])[0].get("id")
    walk_steps: list[dict[str, Any]] = []
    walk_all: dict[str, Any] = {"paths": []}
    if start:
        walk_steps = _bfs(edges, by_id, start)
        walk_all = {"paths": _all_paths(edges, by_id, start)}
    return {"id": record_id, "title": title, "actor": actor, "sections": sections,
            "markdown": markdown, "walk": {"steps": walk_steps}, "walk_all": walk_all}
