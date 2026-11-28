# tests/cli/test_cli_interop.py — план «Интероп-экспорты» Задача 2:
# CLI `interop export --kind dmn|asl|rasa --id [--write PATH] [--force]` —
# derived-артефакты (fm derived_from на записи-источники), review-first,
# CAS + history, дрейф ловится `todoc stale`.
import json
import xml.etree.ElementTree as ET

from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError

FLOW_REC = {
    "schema_version": 1, "record_id": "flow:checkout", "entity_type": "flow",
    "title": "Оформление заказа", "actor": "Покупатель",
    "states": ["created", "paid"], "outcomes": ["paid", "X_OUT"],
    "tree": {
        "nodes": [
            {"id": "start", "type": "action", "prompt": "Старт", "props": {"mode": "auto"}},
            {"id": "q-ok", "type": "question", "prompt": "Ок?", "props": {"mode": "auto"}},
            {"id": "out-bad", "type": "terminal", "prompt": "Отказ",
             "props": {"mode": "auto", "error_code": "X_OUT"}},
            {"id": "out-paid", "type": "terminal", "prompt": "Оплачено", "props": {"mode": "auto"}},
        ],
        "edges": [
            {"from": "start", "to": "q-ok", "priority": 1},
            {"from": "q-ok", "when": "нет", "to": "out-bad", "priority": 1},
            {"from": "q-ok", "when": "да", "to": "out-paid", "priority": 2},
        ],
    },
}

RULE_REC = {
    "schema_version": 1, "record_id": "rule:no-funds-v1", "entity_type": "rule",
    "title": "Недостаток средств даёт отказ оплаты",
    "statement": "Покупатель с недостаточным балансом SHALL получать отказ с кодом X_OUT.",
    "status": "active",
    "examples": [{"given": "баланс покупателя меньше суммы заказа",
                  "when": "покупатель подтверждает оплату",
                  "then": "отказ X_OUT"}],
    "relations": [{"type_id": "belongs_to", "target": {"kind": "record", "id": "flow:checkout"}}],
}

TERM_REC = {
    "schema_version": 1, "record_id": "term:cart", "entity_type": "term",
    "title": "CART", "term_type": "concept",
    "definition": "Корзина хранит товары до оплаты. Корзина очищается после оплаты.",
    "aliases": ["корзина"], "relations": [],
}


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


def _entity_type(tmp_path, type_id, path_dir):
    d = tmp_path / ".todoc" / "entity_types" / type_id
    d.mkdir(parents=True)
    (d / "type.json").write_text(json.dumps(
        {"schema_version": 1, "type_id": type_id, "version": "0.1", "kind": "entity_type",
         "description": type_id, "format": "json",
         "required_fields": ["record_id", "entity_type", "title"],
         "path_template": f"records/{path_dir}/{{slug}}.json"},
        ensure_ascii=False) + "\n", encoding="utf-8")


def _init_interop(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    export_type = tmp_path / ".todoc" / "doc_types" / "export"
    export_type.mkdir(parents=True)
    (export_type / "type.json").write_text(json.dumps(
        {"schema_version": 1, "type_id": "export", "version": "0.1", "kind": "doc_type",
         "description": "Derived-артефакт экспорта.", "format": "markdown"},
        ensure_ascii=False) + "\n", encoding="utf-8")
    rules_file = tmp_path / ".todoc" / "rules" / "document-rules.json"
    rules = json.loads(rules_file.read_text(encoding="utf-8"))
    rules["rules"].append({"id": "fm-export", "match": {"kind": "file", "front_matter": {"doc_type": "export"}},
                           "assign": {"doc_type": "export"}, "priority": 200})
    rules_file.write_text(json.dumps(rules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rel = tmp_path / ".todoc" / "relation_types" / "belongs_to"
    rel.mkdir(parents=True)
    (rel / "type.json").write_text(json.dumps(
        {"schema_version": 1, "type_id": "belongs_to", "version": "0.1", "kind": "relation_type",
         "description": "Правило принадлежит флоу.",
         "endpoints": [{"from": "rule", "to": "flow", "cardinality": "many"}]},
        ensure_ascii=False) + "\n", encoding="utf-8")
    for type_id, path_dir in (("flow", "flows"), ("rule", "rules"), ("term", "terms")):
        _entity_type(tmp_path, type_id, path_dir)
    for rec, sub in ((FLOW_REC, "flows"), (RULE_REC, "rules"), (TERM_REC, "terms")):
        path = tmp_path / "records" / sub / f"{rec['record_id'].split(':', 1)[1]}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)]).exit_code == 0
    return runner


def test_asl_export_to_stdout(tmp_path):
    runner = _init_interop(tmp_path)
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "asl",
                      "--id", "flow:checkout"])
    assert r.exit_code == 0, r.output
    data = _json(r)["data"]["result"]
    assert data["kind"] == "asl" and data["record_id"] == "flow:checkout"
    asl = json.loads(data["artifact"])
    assert asl["StartAt"] == "start" and asl["States"]["q-ok"]["Type"] == "Choice"


def test_dmn_export_to_stdout(tmp_path):
    runner = _init_interop(tmp_path)
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "dmn",
                      "--id", "rule:no-funds-v1"])
    assert r.exit_code == 0, r.output
    data = _json(r)["data"]["result"]
    assert data["kind"] == "dmn"
    table = ET.fromstring(data["artifact"])\
        .find("{https://www.omg.org/spec/DMN/20191111/MODEL/}decision/"
              "{https://www.omg.org/spec/DMN/20191111/MODEL/}decisionTable")
    assert table is not None


def test_rasa_glossary_export_without_id(tmp_path):
    runner = _init_interop(tmp_path)
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "rasa"])
    assert r.exit_code == 0, r.output
    data = _json(r)["data"]["result"]
    assert data["record_id"] is None and "- intent: term_cart" in data["artifact"]


def test_rasa_single_term_export(tmp_path):
    runner = _init_interop(tmp_path)
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "rasa",
                      "--id", "term:cart"])
    assert r.exit_code == 0, r.output
    assert _json(r)["data"]["result"]["artifact"].count("- intent: ") == 1


def test_export_requires_id_for_asl_and_dmn(tmp_path):
    runner = _init_interop(tmp_path)
    for kind in ("asl", "dmn"):
        r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", kind])
        assert r.exit_code != 0
        assert getattr(r.exception, "code", "") == "usage.error"


def test_export_rejects_unknown_record(tmp_path):
    runner = _init_interop(tmp_path)
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "asl",
                      "--id", "flow:missing"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "records.not_found"


def test_export_rejects_wrong_entity_type(tmp_path):
    runner = _init_interop(tmp_path)
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "asl",
                      "--id", "rule:no-funds-v1"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "interop.wrong_entity_type"


def test_dmn_rule_without_flow_relation(tmp_path):
    runner = _init_interop(tmp_path)
    rule_path = tmp_path / "records" / "rules" / "no-funds-v1.json"
    rec = json.loads(rule_path.read_text(encoding="utf-8"))
    rec["relations"] = []
    rule_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)])
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "dmn",
                      "--id", "rule:no-funds-v1"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "interop.flow_missing"


def test_write_only_inside_exports(tmp_path):
    runner = _init_interop(tmp_path)
    r = _run(runner, ["interop", "export", "--apply", "--root", str(tmp_path), "--kind", "asl",
                      "--id", "flow:checkout", "--write", "tasks/x.md"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "interop.write_outside_exports"
    r = _run(runner, ["interop", "export", "--apply", "--root", str(tmp_path), "--kind", "asl",
                      "--id", "flow:checkout", "--write", "../escape.md"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "access.outside_data_root"
    r = _run(runner, ["interop", "export", "--apply", "--root", str(tmp_path), "--kind", "asl",
                      "--id", "flow:checkout", "--write", "/abs/x.md"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "access.outside_data_root"


def test_write_creates_derived_doc_and_is_fresh(tmp_path):
    runner = _init_interop(tmp_path)
    r = _run(runner, ["interop", "export", "--apply", "--root", str(tmp_path), "--kind", "asl",
                      "--id", "flow:checkout", "--write", "exports/asl-checkout.md"])
    assert r.exit_code == 0, r.output
    data = _json(r)["data"]["result"]
    target = tmp_path / "exports" / "asl-checkout.md"
    text = target.read_text(encoding="utf-8")
    fm_lines = text.splitlines()[:text.index("\n---", 3) + 1]
    assert "doc_type: export" in fm_lines
    anchor_line = next(ln for ln in fm_lines if ln.startswith("derived_from:"))
    assert anchor_line.startswith('derived_from: ["records/flows/checkout.json#/tree@sha256:')
    assert "```json" in text and '"StartAt": "start"' in text
    assert data["written"] == "exports/asl-checkout.md"
    assert data["hash"].startswith("sha256:") and data["derived_from"] == 1
    assert _run(runner, ["validate", "--root", str(tmp_path), "--all"]).exit_code == 0
    s = _run(runner, ["stale", "--root", str(tmp_path)])
    assert s.exit_code == 0 and _json(s)["data"]["result"]["stale"] == 0


def test_write_overwrites_derived_target_and_refuses_manual_file(tmp_path):
    runner = _init_interop(tmp_path)
    args = ["interop", "export", "--apply", "--root", str(tmp_path), "--kind", "rasa", "--id", "term:cart",
            "--write", "exports/rasa-cart.md"]
    assert _run(runner, args).exit_code == 0
    assert _run(runner, args).exit_code == 0  # derived-цель (fm derived_from) перезаписывается
    manual = tmp_path / "exports" / "manual.md"
    manual.write_text("---\ntitle: Ручной файл\n---\n\nТекст агента.\n", encoding="utf-8")
    r = _run(runner, ["interop", "export", "--apply", "--root", str(tmp_path), "--kind", "rasa",
                      "--id", "term:cart", "--write", "exports/manual.md"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "interop.target_not_derived"


def test_stale_sees_drift_after_record_edit(tmp_path):
    runner = _init_interop(tmp_path)
    assert _run(runner, ["interop", "export", "--apply", "--root", str(tmp_path), "--kind", "asl",
                         "--id", "flow:checkout", "--write", "exports/asl-checkout.md"]).exit_code == 0
    flow_path = tmp_path / "records" / "flows" / "checkout.json"
    original = flow_path.read_text(encoding="utf-8")
    rec = json.loads(original)
    rec["tree"]["nodes"][0]["prompt"] = "Правка после экспорта"
    flow_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    s = _run(runner, ["stale", "--root", str(tmp_path)])
    assert s.exit_code == 0 and _json(s)["data"]["result"]["stale"] == 1
    assert _json(s)["diagnostics"][0]["code"] == "staleness.dependency_changed"
    flow_path.write_text(original, encoding="utf-8")
    s = _run(runner, ["stale", "--root", str(tmp_path)])
    assert _json(s)["data"]["result"]["stale"] == 0


def test_written_export_is_valid_doc_with_export_type(tmp_path):
    runner = _init_interop(tmp_path)
    assert _run(runner, ["interop", "export", "--apply", "--root", str(tmp_path), "--kind", "dmn",
                         "--id", "rule:no-funds-v1", "--write", "exports/dmn-no-funds.md"]).exit_code == 0
    docs = _run(runner, ["docs", "tree", "--root", str(tmp_path), "--view", "flat", "--output", "json"])
    assert docs.exit_code == 0
    payload = _json(docs)
    paths = [item["path"] for item in payload["data"]["result"]["items"] if item["kind"] == "document"]
    assert "exports/dmn-no-funds.md" in paths


def test_rasa_glossary_without_terms(tmp_path):
    runner = _init_interop(tmp_path)
    (tmp_path / "records" / "terms" / "cart.json").unlink()
    _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)])
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "rasa"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "interop.no_terms"


def test_dmn_related_flow_record_missing(tmp_path):
    runner = _init_interop(tmp_path)
    rule_path = tmp_path / "records" / "rules" / "no-funds-v1.json"
    rec = json.loads(rule_path.read_text(encoding="utf-8"))
    rec["relations"] = [{"type_id": "belongs_to", "target": {"kind": "record", "id": "flow:ghost"}}]
    rule_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)])
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "dmn",
                      "--id", "rule:no-funds-v1"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "interop.flow_missing"


def test_dmn_rejects_non_rule_and_rasa_rejects_non_term(tmp_path):
    runner = _init_interop(tmp_path)
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "dmn",
                      "--id", "term:cart"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "interop.wrong_entity_type"
    r = _run(runner, ["interop", "export", "--root", str(tmp_path), "--kind", "rasa",
                      "--id", "flow:checkout"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "interop.wrong_entity_type"



def test_generated_export_preview_is_read_only_and_stale_hash_is_rejected(tmp_path):
    runner = _init_interop(tmp_path)
    args = ["interop", "export", "--root", str(tmp_path), "--kind", "rasa", "--write", "exports/rasa.md"]
    result = _run(runner, args)
    assert result.exit_code == 0, result.exception
    preview = _json(result)["data"]["result"]
    assert preview["preview"] and "new_content" in preview["plan"]
    assert not (tmp_path / "exports").exists()
    denied = _run(runner, [*args, "--apply", "--if-plan-hash", "stale"])
    assert denied.exception.code == "write.hash_mismatch"
    assert not (tmp_path / "exports").exists()


def test_generated_view_move_preserves_regenerated_payload(tmp_path):
    """A generated export may move, but its fenced artifact is not rewritten."""
    from todoc.application.move import plan_move, apply_move
    from todoc.service import DatasetContext
    runner=_init_interop(tmp_path)
    (tmp_path/'exports/archive').mkdir(parents=True)
    args=['interop','export','--root',str(tmp_path),'--kind','asl','--id','flow:checkout']
    first=_json(_run(runner,args))['data']['result']['artifact']
    r=_run(runner,args+['--write','exports/generated.md','--apply'])
    assert r.exit_code==0,r.output
    ctx=DatasetContext(tmp_path)
    p=plan_move(ctx,source='exports/generated.md',target='exports/archive/generated.md')
    apply_move(ctx,p,if_plan_hash=p.plan_hash)
    r=_run(runner,args+['--write','exports/archive/generated.md','--apply'])
    assert r.exit_code==0,r.output
    assert _json(_run(runner,args))['data']['result']['artifact']==first
    assert first.strip() in (tmp_path/'exports/archive/generated.md').read_text()
