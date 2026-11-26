# tests/unit/test_flow_render.py — план entity-catalog З8 (T1/T2):
# docs flow render/write (витрина из записи, derived_from/stale) + flow walk.
import json

from click.testing import CliRunner

from todoc.adapters.filesystem.scanner import file_hash
from todoc.application.flow_view import build_flow_view
from todoc.cli import cli
from todoc.errors import TodocError

FLOW = {
    "schema_version": 1, "record_id": "flow:order-placement", "entity_type": "flow",
    "title": "Оформление заказа", "actor": "Покупатель",
    "states": ["created", "payment_pending", "paid"],
    "outcomes": ["paid", "ACC_BLOCKED", "INSUFFICIENT_FUNDS", "PAYMENT_RETRY"],
    "origin": {"task": None, "project": "softdoc-profile", "external_id": None},
    "relations": [
        {"type_id": "depends_on", "target": {"kind": "record", "id": "dep:billing"}},
        {"type_id": "uses_term", "target": {"kind": "record", "id": "term:entity-type"}},
    ],
    "tree": {
        "nodes": [
            {"id": "start", "type": "action", "prompt": "Покупатель подтверждает оплату заказа",
             "props": {"mode": "auto"}},
            {"id": "q-account", "type": "question", "prompt": "Аккаунт заблокирован?",
             "props": {"mode": "auto"}},
            {"id": "out-acc", "type": "terminal", "prompt": "Заказ отклоняется",
             "props": {"mode": "auto", "error_code": "ACC_BLOCKED"}},
            {"id": "q-funds", "type": "question", "prompt": "Баланс достаточен?", "props": {"mode": "auto"}},
            {"id": "out-paid", "type": "terminal", "prompt": "Оплачено", "props": {"mode": "auto"}},
        ],
        "edges": [
            {"from": "start", "to": "q-account", "priority": 1},
            {"from": "q-account", "when": "да", "to": "out-acc", "priority": 1},
            {"from": "q-account", "when": "нет", "to": "q-funds", "priority": 2},
            {"from": "q-funds", "when": "нет", "to": "out-paid", "priority": 1},
        ],
    },
}
RULE = {"record_id": "rule:account-blocked-v1", "entity_type": "rule", "title": "Блокировка аккаунта",
        "statement": "Заблокированный аккаунт не проходит оплату.",
        "examples": [{"given": "аккаунт заблокирован", "when": "оформляет заказ",
                      "then": "ACC_BLOCKED"}],
        "status": "active", "origin": {}, "relations": []}
TERM = {"record_id": "term:entity-type", "entity_type": "term", "title": "entity_type",
        "term_type": "concept", "definition": "Тип записи.", "source_path": "glossary/entity-type.md"}


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


# --- flow_view: чистая сборка ---------------------------------------------------

def test_view_sections_present_and_deterministic():
    a = build_flow_view(FLOW, rules=[RULE], terms=[TERM])
    b = build_flow_view(FLOW, rules=[RULE], terms=[TERM])
    assert a == b  # детерминизм
    for key in ("state", "table", "mermaid", "lineage", "terms"):
        assert key in a["sections"] and a["sections"][key].strip(), key
    assert "stateDiagram-v2" in a["sections"]["state"]
    assert "flowchart" in a["sections"]["mermaid"]
    # таблица решений несёт колонку Режим и коды исходов
    assert "Режим" in a["sections"]["table"] and "ACC_BLOCKED" in a["sections"]["table"]
    # правило с кодом в примерах попало в таблицу
    assert "rule:account-blocked-v1" in a["sections"]["table"]
    # lineage из depends_on, термины из uses_term
    assert "dep:billing" in a["sections"]["lineage"]
    assert "term:entity-type" in a["sections"]["terms"]


def test_view_full_markdown_contains_required_sections():
    view = build_flow_view(FLOW, rules=[], terms=[])
    for heading in ("## Жизненный цикл", "## Таблица решений", "## Диаграмма исходов", "## Lineage"):
        assert heading in view["markdown"], heading


# --- walk -----------------------------------------------------------------------

def test_walk_default_path_to_terminal():
    walk = build_flow_view(FLOW, rules=[], terms=[])["walk"]
    ids = [s["node_id"] for s in walk["steps"]]
    assert ids[0] == "start" and ids[-1] == "out-acc"  # ветка минимального приоритета
    assert walk["steps"][-1]["type"] == "terminal"


def test_walk_all_paths_covers_every_terminal():
    walk = build_flow_view(FLOW, rules=[], terms=[])["walk_all"]
    terminals = {p["steps"][-1]["node_id"] for p in walk["paths"]}
    assert terminals == {"out-acc", "out-paid"}, terminals
    assert walk["paths"], "пути не пусты"


def test_walk_from_node():
    walk = build_flow_view(FLOW, rules=[], terms=[], at="q-funds")["walk"]
    assert [s["node_id"] for s in walk["steps"]] == ["q-funds", "out-paid"]


# --- CLI: render / --write / stale ----------------------------------------------

def _init_with_flow(runner, tmp_path, flows_rel="flows/order-placement.md"):
    assert _run(runner, ["init", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    (tmp_path / "flows").mkdir()
    (tmp_path / "records/flows").mkdir(parents=True)
    (tmp_path / "records/flows/order-placement.json").write_text(
        json.dumps(FLOW, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (tmp_path / "records/documents/r.json").parent.mkdir(parents=True)
    (tmp_path / "records/documents/r.json").write_text(
        json.dumps(RULE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (tmp_path / "records/terms/t.json").parent.mkdir(parents=True)
    (tmp_path / "records/terms/t.json").write_text(
        json.dumps(TERM, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert _run(runner, ["index", "rebuild", "--root", str(tmp_path)]).exit_code == 0


def test_cli_render_envelope(tmp_path):
    runner = CliRunner()
    _init_with_flow(runner, tmp_path)
    r = _run(runner, ["docs", "flow", "render", "--root", str(tmp_path), "--id", "flow:order-placement"])
    data = _json(r)["data"]
    assert "Таблица решений" in data["markdown"] and data["id"] == "flow:order-placement"
    s = _json(_run(runner, ["docs", "flow", "render", "--root", str(tmp_path),
                            "--id", "flow:order-placement", "--section", "terms"]))["data"]
    assert s["section"] == "terms" and "term:entity-type" in s["text"]


def test_cli_render_write_and_stale_drift(tmp_path):
    runner = CliRunner()
    _init_with_flow(runner, tmp_path)
    r = _run(runner, ["docs", "flow", "render", "--root", str(tmp_path), "--id", "flow:order-placement",
                      "--write", "flows/order-placement.md"])
    assert _json(r)["data"]["written"] == "flows/order-placement.md"
    text = (tmp_path / "flows/order-placement.md").read_text(encoding="utf-8")
    assert "derived_from" in text and "не править руками" in text.lower()
    assert "## Таблица решений" in text
    # validate в bare-init tmp без зарегистрированных entity/relation типов шумит —
    # проверка validate=0 выполняется на демо-датасете с полной базой типов.
    stale_before = _json(_run(runner, ["stale", "--root", str(tmp_path)]))
    assert stale_before["data"]["stale"] == 0
    # правка записи → дрейф
    rec_text = (tmp_path / "records/flows/order-placement.json").read_text(encoding="utf-8")
    edited = rec_text.replace('"Покупатель подтверждает оплату заказа"',
                              '"Покупатель оплачивает заказ"')
    (tmp_path / "records/flows/order-placement.json").write_text(edited, encoding="utf-8")
    _run(runner, ["index", "rebuild", "--root", str(tmp_path)])
    stale_after = _run(runner, ["stale", "--root", str(tmp_path)])
    assert "staleness" in stale_after.output, stale_after.output


def test_cli_walk_envelope(tmp_path):
    runner = CliRunner()
    _init_with_flow(runner, tmp_path)
    walk = _json(_run(runner, ["docs", "flow", "walk", "--root", str(tmp_path),
                               "--id", "flow:order-placement"]))["data"]
    assert walk["steps"][0]["node_id"] == "start"
    allp = _json(_run(runner, ["docs", "flow", "walk", "--root", str(tmp_path),
                               "--id", "flow:order-placement", "--all-paths"]))["data"]
    assert len(allp["paths"]) == 2
    at = _json(_run(runner, ["docs", "flow", "walk", "--root", str(tmp_path),
                             "--id", "flow:order-placement", "--at", "q-funds"]))["data"]
    assert at["steps"][0]["node_id"] == "q-funds"


def test_cli_render_unknown_flow(tmp_path):
    runner = CliRunner()
    _run(runner, ["init", "--root", str(tmp_path), "--no-input"])
    r = _run(runner, ["docs", "flow", "render", "--root", str(tmp_path), "--id", "flow:ghost"])
    assert r.exit_code == 3 and "flow" in str(r.exception)


# --- покрытие ветвей сборки ------------------------------------------------------

def test_mode_normalises_unknown_and_missing():
    from todoc.application.flow_view import _mode
    assert _mode(None) == "auto"
    assert _mode({}) == "auto"
    assert _mode({"mode": "weird"}) == "auto"
    assert _mode({"mode": "ask-user"}) == "ask-user"


def test_rules_by_belongs_to_and_statement():
    rel_rule = {"record_id": "rule:a-v1", "entity_type": "rule", "title": "A",
                "status": "active", "origin": {}, "relations": [
                    {"type_id": "belongs_to", "target": {"kind": "record", "id": "flow:order-placement"}}]}
    stmt_rule = {"record_id": "rule:b-v1", "entity_type": "rule", "title": "B",
                 "statement": "Без примеров — только формулировка.",
                 "status": "active", "origin": {}, "relations": []}
    view = build_flow_view(FLOW, rules=[rel_rule, stmt_rule], terms=[])
    # belongs_to-ребро выводит правило в lineage; таблица матчит правила по кодам исходов
    assert "rule:a-v1" in view["sections"]["lineage"]
    assert "rule:b-v1" not in view["sections"]["lineage"]  # без belongs_to — не правило флоу
    assert "rule:a-v1" not in view["sections"]["table"]  # в таблице — только коды исходов


def test_rule_condition_and_then_branches():
    from todoc.application.flow_view import _rule_condition, _rule_then
    assert _rule_condition({"examples": [{"given": "г", "when": "к"}]}) == "г; к"
    assert _rule_condition({"examples": [{"given": "г"}]}) == "г"
    assert _rule_condition({"statement": "формулировка"}) == "формулировка"
    assert _rule_condition({}) == "—"
    assert _rule_then({"examples": [{"then": "X"}]}) == "X"
    assert _rule_then({}) == "—"
    assert _rule_then({"examples": [{"then": ""}]}) == "—"


def test_flow_without_tree_and_without_deps():
    bare = {k: v for k, v in FLOW.items() if k not in ("tree", "relations")}
    view = build_flow_view(bare, rules=[], terms=[])
    assert view["sections"]["table"] == "" and view["sections"]["mermaid"] == ""
    assert view["sections"]["lineage"] == "" and view["sections"]["terms"] == ""
    assert view["sections"]["state"].strip() != ""
    assert "## Жизненный цикл" in view["markdown"]
    assert view["walk"]["steps"] == [] and view["walk_all"]["paths"] == []


def test_term_without_definition_and_edge_to_missing_node():
    term_nodef = {"record_id": "term:x", "entity_type": "term", "title": "X",
                  "term_type": "concept", "source_path": "glossary/x.md"}
    broken_tree = {
        "nodes": [
            {"id": "start", "type": "action", "prompt": "s", "props": {"mode": "auto"}},
            {"id": "term1", "type": "terminal", "prompt": "t", "props": {"mode": "auto"}},
        ],
        "edges": [
            {"from": "start", "to": "ghost", "priority": 1},   # узел отсутствует
            {"from": "start", "to": "term1", "priority": 2},
            {"from": "term1", "to": "start", "priority": 1},   # цикл из терминала
        ],
    }
    rec = {**FLOW, "tree": broken_tree, "relations": [
        {"type_id": "uses_term", "target": {"kind": "record", "id": "term:x"}}]}
    view = build_flow_view(rec, rules=[], terms=[term_nodef])
    # минимальный приоритет ведёт в ghost: walk останавливается (висячее ребро видно),
    # а не молча пропускает его
    assert [s["node_id"] for s in view["walk"]["steps"]] == ["start"]
    assert view["walk"]["steps"][-1]["type"] != "terminal"
    paths = view["walk_all"]["paths"]
    assert {p["steps"][-1]["node_id"] for p in paths} == {"term1"}  # все пути — через term1
    assert "`term:x` — X" in view["sections"]["terms"]  # без «: определение»


def test_walk_cycle_guard_bfs():
    cyclic_tree = {
        "nodes": [
            {"id": "start", "type": "action", "prompt": "s", "props": None},
            {"id": "loop", "type": "action", "prompt": "l", "props": {"mode": "ask-user"}},
            {"id": "end", "type": "terminal", "prompt": "e", "props": {"mode": "auto"}},
        ],
        "edges": [
            {"from": "start", "to": "loop", "priority": 1},
            {"from": "loop", "to": "start", "priority": 1},  # цикл start→loop→start
            {"from": "loop", "to": "end", "priority": 2},
        ],
    }
    rec = {**FLOW, "tree": cyclic_tree}
    view = build_flow_view(rec, rules=[], terms=[])
    ids = [s["node_id"] for s in view["walk"]["steps"]]
    assert ids == ["start", "loop"]  # priority-1 — ребро цикла; seen-множество разрывает обход
    assert view["walk"]["steps"][-1]["type"] == "action"
    assert [s["mode"] for s in view["walk"]["steps"]] == ["auto", "ask-user"]
    paths = view["walk_all"]["paths"]
    # все пути ациклические: ребро обратно в start пропускается
    assert {tuple(s["node_id"] for s in p["steps"]) for p in paths} == {("start", "loop", "end")}


def test_bfs_priority_tie_sorted_by_target():
    tie_tree = {
        "nodes": [
            {"id": "start", "type": "question", "prompt": "s", "props": {"mode": "auto"}},
            {"id": "b-out", "type": "terminal", "prompt": "b", "props": {"mode": "auto"}},
            {"id": "a-out", "type": "terminal", "prompt": "a", "props": {"mode": "auto"}},
        ],
        "edges": [
            {"from": "start", "to": "b-out", "priority": 1},
            {"from": "start", "to": "a-out", "priority": 1},  # равный приоритет → алфавит
        ],
    }
    rec = {**FLOW, "tree": tie_tree}
    view = build_flow_view(rec, rules=[], terms=[])
    assert view["walk"]["steps"][-1]["node_id"] == "a-out"


# --- CLI: границы ----------------------------------------------------------------

def test_cli_render_section_empty(tmp_path):
    runner = CliRunner()
    _init_with_flow(runner, tmp_path)
    r = _run(runner, ["docs", "flow", "render", "--root", str(tmp_path),
                      "--id", "flow:order-placement", "--section", "lineage"])
    assert r.exit_code == 0  # lineage есть (dep:billing)
    no_dep = json.loads(json.dumps(FLOW))
    no_dep["relations"] = []
    (tmp_path / "records/flows/order-placement.json").write_text(
        json.dumps(no_dep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _run(runner, ["index", "rebuild", "--root", str(tmp_path)])
    r2 = _run(runner, ["docs", "flow", "render", "--root", str(tmp_path),
                       "--id", "flow:order-placement", "--section", "lineage"])
    assert r2.exit_code == 3 and "empty" in str(r2.exception)


def test_cli_render_write_refuses_manual_file(tmp_path):
    runner = CliRunner()
    _init_with_flow(runner, tmp_path)
    target = tmp_path / "flows/order-placement.md"
    target.write_text("# Ручной файл\n\nТекст без derived_from.\n", encoding="utf-8")
    r = _run(runner, ["docs", "flow", "render", "--root", str(tmp_path),
                      "--id", "flow:order-placement", "--write", "flows/order-placement.md"])
    assert r.exit_code == 5 and "derived_from" in str(r.exception)
    assert "Ручной файл" in target.read_text(encoding="utf-8")  # не перезаписан


def test_cli_render_write_outside_root(tmp_path):
    runner = CliRunner()
    _init_with_flow(runner, tmp_path)
    r = _run(runner, ["docs", "flow", "render", "--root", str(tmp_path),
                      "--id", "flow:order-placement", "--write", "../escape.md"])
    assert r.exit_code != 0
    assert not (tmp_path.parent / "escape.md").exists()


def test_cli_flow_not_found_for_walk(tmp_path):
    runner = CliRunner()
    _run(runner, ["init", "--root", str(tmp_path), "--no-input"])
    r = _run(runner, ["docs", "flow", "walk", "--root", str(tmp_path), "--id", "flow:ghost"])
    assert r.exit_code == 3 and "flow" in str(r.exception)


def test_state_section_without_states():
    bare = {k: v for k, v in FLOW.items() if k not in ("tree", "relations", "states")}
    view = build_flow_view(bare, rules=[], terms=[])
    assert "[*] --> start" in view["sections"]["state"]
    assert "start --> [*]" in view["sections"]["state"]
    assert "Исходы:" in view["sections"]["state"]  # outcomes присутствуют
    no_out = {k: v for k, v in FLOW.items() if k not in ("tree", "relations", "outcomes")}
    assert "Исходы:" not in build_flow_view(no_out, rules=[], terms=())["sections"]["state"]


def test_lineage_rules_without_deps():
    rel_rule = {"record_id": "rule:a-v1", "entity_type": "rule", "title": "A",
                "status": "active", "origin": {}, "relations": [
                    {"type_id": "belongs_to", "target": {"kind": "record", "id": "flow:order-placement"}}]}
    no_dep = {k: v for k, v in FLOW.items() if k != "relations"}
    view = build_flow_view(no_dep, rules=[rel_rule], terms=[])
    assert "Зависимости" not in view["sections"]["lineage"]
    assert "Правила флоу:" in view["sections"]["lineage"] and "rule:a-v1" in view["sections"]["lineage"]
