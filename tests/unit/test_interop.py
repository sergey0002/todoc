# tests/unit/test_interop.py — план «Интероп-экспорты» Задача 1:
# тест-контракты маппинга записей (flow/tree, rule/examples, term) на целевые
# форматы ASL / DMN 1.3 / Rasa NLU. Источник контракта — §1–§4 плана
# demo/plan/interop-exports-dmn-asl-rasa.md и структуры демо-записей.
import pytest

from todoc.application.interop import (
    definition_examples,
    find_error_code,
    first_node,
    intent_name,
    ordered_branches,
    question_before,
    related_flow_id,
    terminal_for_code,
    yes_outcome,
)
from todoc.errors import ValidationError

# --- фикстуры: минимальные записи, повторяющие форму демо-датасета ------------

FLOW = {
    "schema_version": 1,
    "record_id": "flow:checkout",
    "entity_type": "flow",
    "title": "Оформление заказа",
    "actor": "Покупатель",
    "states": ["created", "paid"],
    "outcomes": ["paid", "X_OUT"],
    "tree": {
        "nodes": [
            {"id": "start", "type": "action", "prompt": "Старт", "props": {"mode": "auto"}},
            {"id": "q-ok", "type": "question", "prompt": "Ок?", "props": {"mode": "auto"}},
            {"id": "out-bad", "type": "terminal", "prompt": "Отказ",
             "props": {"mode": "auto", "error_code": "X_OUT"}},
            {"id": "out-paid", "type": "terminal", "prompt": "Оплачено", "props": {"mode": "auto"}},
        ],
        "edges": [
            {"from": "q-ok", "when": "да", "to": "out-paid", "priority": 2},
            {"from": "start", "to": "q-ok", "priority": 1},
            {"from": "q-ok", "when": "нет", "to": "out-bad", "priority": 1},
        ],
    },
}

RULE = {
    "schema_version": 1,
    "record_id": "rule:no-funds-v1",
    "entity_type": "rule",
    "title": "Недостаток средств даёт отказ оплаты",
    "statement": "Покупатель с недостаточным балансом SHALL получать отказ с кодом X_OUT.",
    "status": "active",
    "examples": [
        {"given": "баланс покупателя меньше суммы заказа",
         "when": "покупатель подтверждает оплату",
         "then": "отказ X_OUT, заказ остаётся в payment_pending"},
    ],
    "relations": [
        {"type_id": "belongs_to", "target": {"kind": "record", "id": "flow:checkout"}},
    ],
}

TERM = {
    "schema_version": 1,
    "record_id": "term:cart",
    "entity_type": "term",
    "title": "CART",
    "term_type": "concept",
    "definition": "Корзина хранит товары до оплаты. Корзина очищается после оплаты.",
    "aliases": ["корзина"],
}


# --- контракт: flow/tree -------------------------------------------------------

def test_first_node_is_node_without_incoming_edges():
    assert first_node(FLOW["tree"]) == "start"


def test_first_node_falls_back_to_first_node_when_cycle():
    cyclic = {"nodes": FLOW["tree"]["nodes"],
              "edges": FLOW["tree"]["edges"] + [{"from": "out-paid", "to": "start", "priority": 9}]}
    assert first_node(cyclic) == "start"


def test_ordered_branches_sort_by_priority_stable():
    branches = ordered_branches(FLOW["tree"], "q-ok")
    assert [(b["when"], b["to"]) for b in branches] == [("нет", "out-bad"), ("да", "out-paid")]


# --- контракт: rule → DMN ------------------------------------------------------

def test_find_error_code_takes_first_allcaps_token():
    assert find_error_code(RULE["statement"]) == "X_OUT"


def test_find_error_code_rejects_text_without_code():
    with pytest.raises(ValidationError) as exc:
        find_error_code("Правило без кода ошибки.")
    assert exc.value.code == "interop.no_error_code"


def test_related_flow_id_follows_belongs_to():
    assert related_flow_id(RULE) == "flow:checkout"


def test_related_flow_id_ignores_non_flow_relations():
    rule = {**RULE, "relations": [
        {"type_id": "implements", "target": {"kind": "document", "id": "doc:plan-x"}}]}
    with pytest.raises(ValidationError) as exc:
        related_flow_id(rule)
    assert exc.value.code == "interop.flow_missing"


def test_terminal_for_code_finds_failure_terminal():
    node = terminal_for_code(FLOW["tree"], "X_OUT")
    assert node["id"] == "out-bad" and node["props"]["error_code"] == "X_OUT"


def test_terminal_for_code_rejects_unknown_code():
    with pytest.raises(ValidationError) as exc:
        terminal_for_code(FLOW["tree"], "Y_OTHER")
    assert exc.value.code == "interop.no_terminal_for_code"


def test_question_before_prefers_net_branch():
    assert question_before(FLOW["tree"], "out-bad")["id"] == "q-ok"


def test_question_before_falls_back_to_any_incoming_edge():
    node = question_before(FLOW["tree"], "out-paid")
    assert node["id"] == "q-ok"


def test_question_before_rejects_root_terminal():
    with pytest.raises(ValidationError) as exc:
        question_before(FLOW["tree"], "start")
    assert exc.value.code == "interop.no_question"


def test_yes_outcome_follows_da_chain_to_success_terminal():
    assert yes_outcome(FLOW["tree"], "q-ok") == "paid"


def test_yes_outcome_rejects_broken_chain():
    broken = {"nodes": FLOW["tree"]["nodes"][:3], "edges": FLOW["tree"]["edges"][:2]}
    with pytest.raises(ValidationError) as exc:
        yes_outcome(broken, "q-ok")
    assert exc.value.code == "interop.yes_branch_missing"


# --- контракт: term → Rasa NLU -------------------------------------------------

def test_intent_name_is_record_local_part():
    assert intent_name("term:cart") == "term_cart"


def test_definition_examples_split_sentences():
    examples = definition_examples(TERM)
    assert examples == ["Корзина хранит товары до оплаты.",
                        "Корзина очищается после оплаты."]


def test_definition_examples_drops_empty_fragments():
    term = {**TERM, "definition": "Одно предложение.  \n  "}
    assert definition_examples(term) == ["Одно предложение."]


def test_yes_outcome_rejects_infinite_da_cycle():
    cyclic = {"nodes": [
        {"id": "q1", "type": "question", "prompt": "1?", "props": {"mode": "auto"}},
        {"id": "q2", "type": "question", "prompt": "2?", "props": {"mode": "auto"}},
    ], "edges": [
        {"from": "q1", "when": "да", "to": "q2", "priority": 1},
        {"from": "q2", "when": "да", "to": "q1", "priority": 1},
    ]}
    with pytest.raises(ValidationError) as exc:
        yes_outcome(cyclic, "q1")
    assert exc.value.code == "interop.yes_branch_missing"


def test_question_before_rejects_edge_to_unknown_node():
    ghost = {"nodes": [FLOW["tree"]["nodes"][2]], "edges": [{"from": "ghost", "to": "out-bad", "priority": 1}]}
    with pytest.raises(ValidationError) as exc:
        question_before(ghost, "out-bad")
    assert exc.value.code == "interop.no_node"


def test_yes_outcome_rejects_question_without_da_branch():
    only_net = {"nodes": FLOW["tree"]["nodes"][:3], "edges": FLOW["tree"]["edges"][2:]}
    with pytest.raises(ValidationError) as exc:
        yes_outcome(only_net, "q-ok")
    assert exc.value.code == "interop.yes_branch_missing"

# --- Задача 2: генераторы артефактов ------------------------------------------

from todoc.application.interop import (
    anchor_for,
    build_export_doc,
    flow_to_asl,
    rule_to_dmn,
    terms_to_rasa,
)


def test_flow_to_asl_states_and_branches():
    asl = flow_to_asl(FLOW)
    assert asl["StartAt"] == "start"
    states = asl["States"]
    assert states["start"]["Type"] == "Task"
    assert states["start"]["Resource"] == "todoc:start"
    assert states["start"]["Next"] == "q-ok"
    choice = states["q-ok"]
    assert choice["Type"] == "Choice"
    assert choice["Choices"] == [
        {"Variable": "$.q-ok", "StringEquals": "нет", "Next": "out-bad"},
        {"Variable": "$.q-ok", "StringEquals": "да", "Next": "out-paid"},
    ]
    assert states["out-bad"] == {"Type": "Fail", "Error": "X_OUT", "Cause": "Отказ"}
    assert states["out-paid"] == {"Type": "Succeed"}
    assert "flow:checkout" in asl["Comment"]


def test_flow_to_asl_action_without_outgoing_edges_ends():
    flow = {"record_id": "flow:end", "title": "Тупик",
            "tree": {"nodes": [{"id": "a", "type": "action", "prompt": "Финиш", "props": {}}],
                     "edges": []}}
    asl = flow_to_asl(flow)
    assert asl["States"]["a"] == {"Type": "Task", "Resource": "todoc:a", "End": True}
    assert asl["StartAt"] == "a"


def test_flow_to_asl_question_with_unconditioned_edge_uses_default():
    tree = {"nodes": [
        {"id": "q", "type": "question", "prompt": "?", "props": {"mode": "auto"}},
        {"id": "any", "type": "terminal", "prompt": "иначе", "props": {}},
    ], "edges": [{"from": "q", "to": "any", "priority": 3}]}
    asl = flow_to_asl({"tree": tree})
    assert asl["States"]["q"] == {"Type": "Choice", "Choices": [], "Default": "any"}


def test_flow_to_asl_default_takes_first_unconditioned_edge():
    tree = {"nodes": [
        {"id": "q", "type": "question", "prompt": "?", "props": {"mode": "auto"}},
        {"id": "first", "type": "terminal", "prompt": "иначе 1", "props": {}},
        {"id": "second", "type": "terminal", "prompt": "иначе 2", "props": {}},
    ], "edges": [{"from": "q", "to": "second", "priority": 7},
                 {"from": "q", "to": "first", "priority": 3}]}
    asl = flow_to_asl({"tree": tree})
    assert asl["States"]["q"]["Default"] == "first"


def test_rule_to_dmn_decision_table_structure():
    import xml.etree.ElementTree as ET
    xml_text = rule_to_dmn(RULE, FLOW)
    root = ET.fromstring(xml_text)
    assert root.tag == "{https://www.omg.org/spec/DMN/20191111/MODEL/}definitions"
    decision = root.find("{https://www.omg.org/spec/DMN/20191111/MODEL/}decision")
    assert decision is not None and decision.get("name") == RULE["title"]
    table = decision.find("{https://www.omg.org/spec/DMN/20191111/MODEL/}decisionTable")
    assert table is not None and table.get("hitPolicy") == "UNIQUE"
    ns = "{https://www.omg.org/spec/DMN/20191111/MODEL/}"
    labels = [i.get("label") for i in table.findall(ns + "input")]
    assert labels == ["Ситуация", "Условие", "Режим"]
    outputs = [o.get("label") for o in table.findall(ns + "output")]
    assert outputs == ["Исход"]
    rules = table.findall(ns + "rule")
    assert len(rules) == 2
    entries1 = [t.text for t in rules[0].findall(f"{ns}inputEntry/{ns}text")]
    assert entries1 == ["баланс покупателя меньше суммы заказа",
                        "покупатель подтверждает оплату", "auto"]
    assert [t.text for t in rules[0].findall(f"{ns}outputEntry/{ns}text")] == ["X_OUT"]
    entries2 = [t.text for t in rules[1].findall(f"{ns}inputEntry/{ns}text")]
    assert entries2 == [None, "да", "auto"]  # пустой inputEntry = «любое значение»
    assert [t.text for t in rules[1].findall(f"{ns}outputEntry/{ns}text")] == ["paid"]


def test_rule_to_dmn_escapes_xml_specials():
    rule = {**RULE, "title": "Отказ <b>сильно</b> & \"жёстко\""}
    import xml.etree.ElementTree as ET
    root = ET.fromstring(rule_to_dmn(rule, FLOW))
    decision = root.find("{https://www.omg.org/spec/DMN/20191111/MODEL/}decision")
    assert decision.get("name") == "Отказ <b>сильно</b> & \"жёстко\""


def test_terms_to_rasa_nlu_block():
    term2 = {**TERM, "record_id": "term:audit", "title": "AUDIT",
             "definition": "Аудит проверяет датасет."}
    yml = terms_to_rasa([TERM, term2])
    assert yml.startswith('version: "3.1"\nnlu:\n')
    assert yml.index("- intent: term_audit") < yml.index("- intent: term_cart")
    assert "    - Корзина хранит товары до оплаты." in yml
    assert "    - Корзина очищается после оплаты." in yml
    assert "    - Аудит проверяет датасет." in yml


def test_anchor_for_hashes_json_pointer(tmp_path):
    import json as _json
    rec = tmp_path / "records" / "x.json"
    rec.parent.mkdir(parents=True)
    rec.write_text(_json.dumps({"tree": {"nodes": [1]}}, ensure_ascii=False), encoding="utf-8")
    anchor = anchor_for(tmp_path, "records/x.json", "/tree")
    assert anchor.startswith("records/x.json#/tree@sha256:")
    dep = {"path": "records/x.json", "pointer": "/tree"}
    from todoc.application.staleness import fragment_hash, parse_anchor
    parsed = parse_anchor(anchor)
    assert parsed is not None
    actual, status = fragment_hash(tmp_path, parsed)
    assert status == "ok" and actual == parsed["hash"]


def test_anchor_for_rejects_missing_pointer(tmp_path):
    rec = tmp_path / "records" / "x.json"
    rec.parent.mkdir(parents=True)
    rec.write_text("{\"other\": 1}", encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        anchor_for(tmp_path, "records/x.json", "/tree")
    assert exc.value.code == "interop.anchor_failed"


def test_build_export_doc_front_matter_and_body():
    doc = build_export_doc(
        doc_id="doc:export-asl-checkout", title="Экспорт ASL: flow:checkout",
        kind="asl", anchors=["records/flows/checkout.json#/tree@sha256:abc"],
        artifact='{"StartAt": "start"}', lang="json", today="2026-11-26")
    lines = doc.splitlines()
    assert lines[0] == "---" and "id: doc:export-asl-checkout" in lines
    assert "doc_type: export" in lines
    assert 'derived_from: ["records/flows/checkout.json#/tree@sha256:abc"]' in lines
    assert "tags: [export, interop, asl]" in lines
    assert lines[-2] == "```" or lines[-1] == ""
    assert "```json" in doc and '"StartAt": "start"' in doc
    assert "todoc interop export" in doc and "todoc stale" in doc


def test_terminal_for_code_accepts_action_with_error_code():
    # компенсационная ветка: action-узел с error_code (PAYMENT_RETRY в демо)
    tree = {"nodes": FLOW["tree"]["nodes"] + [
        {"id": "out-retry", "type": "action", "prompt": "Повтор",
         "props": {"mode": "auto", "error_code": "PAYMENT_RETRY"}}],
        "edges": FLOW["tree"]["edges"]}
    node = terminal_for_code(tree, "PAYMENT_RETRY")
    assert node["id"] == "out-retry"
    with pytest.raises(ValidationError) as exc:
        terminal_for_code(tree, "GHOST_CODE")
    assert exc.value.code == "interop.no_terminal_for_code"
