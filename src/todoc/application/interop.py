"""Interop exports: записи → внешние форматы (ASL, DMN 1.3, Rasa NLU YML).

План ``demo/plan/interop-exports-dmn-asl-rasa.md``. Запись — единственная истина;
конвертеры чистые (без I/O) и только читают. Контракт маппинга зафиксирован в
докстроках и тест-контрактах ``tests/unit/test_interop.py`` (Задача 1); генераторы
форматного текста и CLI — Задача 2.

Контракт маппинга (источники — структуры демо-записей):

flow/tree → ASL (Amazon States Language, JSON):
- ``StartAt`` — первый узел без входящих рёбер (``first_node``);
- ``States`` — по узлу дерева: question → ``Choice`` (``Choices`` по рёбрам с
  ``when``, упорядоченным по ``priority``: ``Variable = $.<node>``,
  ``StringEquals = when``; безусловное ребро → ``Default``); action → ``Task``
  (``Resource = todoc:<node>``, ``Next`` = первое исходящее ребро, без рёбер —
  ``End: true``); terminal с ``props.error_code`` → ``Fail`` (``Error``/``Cause`` =
  prompt), terminal без кода → ``Succeed``.

rule → DMN 1.3 (decision table):
- код отказа — первый ALLCAPS-токен statement (``find_error_code``);
- флоу правила — единственная связь ``belongs_to`` на ``flow:*``
  (``related_flow_id``);
- терминал отказа — terminal дерева с ``props.error_code`` == код
  (``terminal_for_code``); вопрос отказа — узел перед ним по ребру ``when=нет``
  (``question_before``); успешный исход — терминал, достижимый из вопроса только
  по рёбрам ``when=да`` (``yes_outcome``), метка = код терминала или id без
  префикса ``out-``;
- таблица: колонки ввода «Ситуация» (example.given), «Условие» (example.when),
  «Режим» (props.mode вопроса), выход «Исход»; строка на каждый example
  (→ код отказа) + комплементарная строка бинарной ветви «да» (→ успешный исход),
  ``hitPolicy="UNIQUE"``.

term → Rasa NLU YML:
- интент — ``term_<slug>`` (``intent_name``); examples — предложения definition
  (``definition_examples``), каждый — отдельная строка ``- …`` в block scalar.
"""

from __future__ import annotations

import re
from typing import Any

from todoc.errors import ValidationError

_ERROR_CODE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")


def _nodes(tree: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for n in (tree.get("nodes") or []) if isinstance(n, dict) and n.get("id")]


def _edges(tree: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in (tree.get("edges") or []) if isinstance(e, dict) and e.get("from") and e.get("to")]


def _node(tree: dict[str, Any], node_id: str) -> dict[str, Any]:
    for node in _nodes(tree):
        if node["id"] == node_id:
            return node
    raise ValidationError(f"Node not found in flow tree: {node_id}", "interop.no_node")


#: RFC-2119 ключевые слова требований — не коды отказа (демо-стейтменты
#: написаны по конвенции «SHALL … с кодом INSUFFICIENT_FUNDS»).
_RFC2119 = {"SHALL", "MUST", "SHOULD", "MAY", "NOT", "REQUIRED", "RECOMMENDED", "OPTIONAL"}


def find_error_code(text: str) -> str:
    """Первый ALLCAPS-токен statement (≥3 знаков, [A-Z0-9_]) — код отказа правила.

    RFC-2119 ключевые слова (SHALL/MUST/…) кодами не считаются.
    """
    for match in _ERROR_CODE.finditer(text or ""):
        if match.group(0) not in _RFC2119:
            return match.group(0)
    raise ValidationError("Statement declares no ALLCAPS error code.", "interop.no_error_code")


def related_flow_id(rule: dict[str, Any]) -> str:
    """Id флоу правила: единственная связь belongs_to на запись flow:*."""
    for rel in rule.get("relations") or []:
        target = rel.get("target") or {}
        if rel.get("type_id") == "belongs_to" and target.get("kind") == "record" \
                and str(target.get("id") or "").startswith("flow:"):
            return str(target["id"])
    raise ValidationError("Rule has no belongs_to relation to a flow record.", "interop.flow_missing")


def terminal_for_code(tree: dict[str, Any], code: str) -> dict[str, Any]:
    """Terminal-узел дерева с props.error_code == code — исход отказа правила."""
    for node in _nodes(tree):
        if node.get("type") == "terminal" and (node.get("props") or {}).get("error_code") == code:
            return node
    raise ValidationError(f"No terminal with error_code {code!r} in flow tree.", "interop.no_terminal_for_code")


def question_before(tree: dict[str, Any], node_id: str) -> dict[str, Any]:
    """Узел-вопрос перед терминалом: ребро с when=«нет», иначе любое входящее."""
    incoming = [e for e in _edges(tree) if e["to"] == node_id]
    net = next((e for e in incoming if e.get("when") == "нет"), None)
    chosen = net or (incoming[0] if incoming else None)
    if chosen is None:
        raise ValidationError(f"No incoming edge for node {node_id}.", "interop.no_question")
    return _node(tree, chosen["from"])


def yes_outcome(tree: dict[str, Any], question_id: str) -> str:
    """Метка успешного исхода: терминал по цепочке рёбер when=«да» от вопроса.

    Метка = props.error_code терминала, а без кода — id без префикса ``out-``.
    """
    current = question_id
    for _ in range(len(_nodes(tree)) + 1):
        edges = [e for e in _edges(tree) if e["from"] == current and e.get("when") == "да"]
        if not edges:
            raise ValidationError(
                f"No да-branch path from question {question_id} to a terminal.",
                "interop.yes_branch_missing")
        current = edges[0]["to"]
        node = next((n for n in _nodes(tree) if n["id"] == current), None)
        if node is None:
            raise ValidationError(
                f"да-branch from {question_id} reaches node {current!r} missing from the tree.",
                "interop.yes_branch_missing")
        if node.get("type") == "terminal":
            code = (node.get("props") or {}).get("error_code")
            return str(code) if code else str(node["id"]).removeprefix("out-")
    raise ValidationError(f"да-branch from {question_id} does not terminate.", "interop.yes_branch_missing")


def first_node(tree: dict[str, Any]) -> str:
    """Id стартового узла ASL: без входящих рёбер; при циклах — первый узел дерева."""
    nodes = _nodes(tree)
    targets = {e["to"] for e in _edges(tree)}
    for node in nodes:
        if node["id"] not in targets:
            return str(node["id"])
    return str(nodes[0]["id"]) if nodes else ""


def ordered_branches(tree: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    """Исходящие рёбра узла, упорядоченные по priority (устойчиво)."""
    edges = [e for e in _edges(tree) if e["from"] == node_id]
    return sorted(edges, key=lambda e: e.get("priority") or 0)


def intent_name(record_id: str) -> str:
    """Имя интента Rasa: локальная часть record_id с ``:`` → ``_``."""
    return record_id.replace(":", "_")


def definition_examples(term: dict[str, Any]) -> list[str]:
    """Предложения definition — examples интента Rasa (пустые фрагменты отбрасываются)."""
    definition = str(term.get("definition") or "")
    fragments = re.split(r"(?<=[.!?])\s+", definition.replace("\n", " ").strip())
    return [f.strip() for f in fragments if f.strip()]
