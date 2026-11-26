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
