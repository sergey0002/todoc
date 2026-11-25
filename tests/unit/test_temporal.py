"""Фаза 3 (K40, K41): би-темпоральные поля, точка во времени, инвалидация."""

from __future__ import annotations

import json

import pytest

from todoc.application import temporal as T
from todoc.application.history import record_write
from todoc.application.query import query_records
from todoc.application.validator import validate_relations


def _record(record_id: str, entity_type: str = "person", **fields):
    data = {"record_id": record_id, "entity_type": entity_type, **fields}
    return {"record_id": record_id, "entity_type": entity_type, "path": f"records/{record_id}.json",
            "data": data}


def _rel(source: str, target: str, type_id: str = "performed_by", **fields):
    return {"type_id": type_id, "source_id": source, "target_id": target, "dataset_id": "d", **fields}


# --- нормализация момента ----------------------------------------------------


@pytest.mark.parametrize("value,expected", [
    (None, None),
    ("", None),
    ("   ", None),
    ("2024-01-01", "2024-01-01"),
    ("2024-01-01T10:00:00Z", "2024-01-01T10:00:00Z"),
    ("2024-01-01t10:00:00z", "2024-01-01T10:00:00Z"),
    ("2024-01-01T10:00:00", "2024-01-01T10:00:00Z"),
    ("2024-01-01T12:00:00+03:00", "2024-01-01T09:00:00Z"),
    ("2024-01-01T10:00:00.500Z", "2024-01-01T10:00:00Z"),
])
def test_normalize_instant(value, expected):
    assert T.normalize_instant(value) == expected


def test_normalize_instant_rejects_garbage():
    with pytest.raises(T.InvalidInstant):
        T.normalize_instant("вчера")


def test_date_only_sorts_before_same_day_instant():
    """Дата — это полночь: она раньше любого момента того же дня."""
    assert T.normalize_instant("2024-01-01") < T.normalize_instant("2024-01-01T00:00:01Z")
    assert T.normalize_instant("2024-01-01") < T.normalize_instant("2024-01-02")


# --- дефекты интервала -------------------------------------------------------


def test_interval_defect_absent_when_no_fields():
    assert T.interval_defect({}) is None
    assert T.interval_defect({"valid_from": "2024-01-01"}) is None


def test_interval_defect_on_inverted_interval():
    defect = T.interval_defect({"valid_from": "2024-06-01", "valid_to": "2024-01-01"})
    assert defect is not None
    code, message, field = defect
    assert code == "temporal.invalid_interval"
    assert field == "valid_to"
    assert "valid_to" in message


def test_interval_defect_on_equal_bounds():
    """Полуоткрытый интервал: valid_to == valid_from — это пустой интервал."""
    defect = T.interval_defect({"valid_from": "2024-01-01", "valid_to": "2024-01-01"})
    assert defect is not None and defect[0] == "temporal.invalid_interval"


def test_interval_defect_names_the_unparseable_field():
    assert T.interval_defect({"valid_from": "не дата"})[2] == "valid_from"
    assert T.interval_defect({"valid_from": "2024-01-01", "valid_to": "позже"})[2] == "valid_to"
    assert T.interval_defect({"valid_to": "не дата"})[0] == "temporal.invalid_instant"


# --- время правды и время знания --------------------------------------------


def test_is_valid_at_is_half_open():
    fields = {"valid_from": "2024-01-01", "valid_to": "2024-06-30"}
    assert T.is_valid_at(fields, "2023-12-31") is False
    assert T.is_valid_at(fields, "2024-01-01") is True     # левая граница включена
    assert T.is_valid_at(fields, "2024-03-15") is True
    assert T.is_valid_at(fields, "2024-06-30") is False    # правая граница исключена
    assert T.is_valid_at(fields, "2024-07-01") is False


def test_is_valid_at_with_open_bounds():
    assert T.is_valid_at({"valid_to": "2024-06-30"}, "2020-01-01") is True
    assert T.is_valid_at({"valid_from": "2024-01-01"}, "2099-01-01") is True
    assert T.is_valid_at({}, "2024-01-01") is True
    assert T.is_valid_at({"valid_from": "2024-01-01"}, None) is True


def test_is_valid_at_is_false_on_unparseable_data():
    """Недетерминированного порядка по мусору в данных не бывает: факт невидим."""
    assert T.is_valid_at({"valid_from": "примерно май"}, "2024-01-01") is False


def test_unparseable_as_of_is_an_error_not_an_empty_answer():
    """Опечатка в точке во времени обязана быть ошибкой, а не молчаливым «ничего»."""
    with pytest.raises(T.InvalidInstant):
        T.is_valid_at({"valid_from": "2024-01-01"}, "не момент")
    with pytest.raises(T.InvalidInstant):
        T.is_superseded({}, "не момент")


def test_is_superseded():
    assert T.is_superseded({}, "2024-01-01") is False
    assert T.is_superseded({"superseded_at": "2024-06-01"}, "2024-07-01") is True
    assert T.is_superseded({"superseded_at": "2024-06-01"}, "2024-05-01") is False
    # Без точки во времени закрытый факт уже не правда о настоящем.
    assert T.is_superseded({"superseded_at": "2024-06-01"}, None) is True
    assert T.is_superseded({}, None) is False
    assert T.is_superseded({"superseded_at": "мусор"}, "2024-01-01") is True


def test_visible_at_combines_both_clocks():
    fields = {"valid_from": "2024-01-01", "valid_to": "2024-12-31", "superseded_at": "2024-06-01"}
    assert T.visible_at(fields, "2024-03-01") is True
    assert T.visible_at(fields, "2024-09-01") is False   # правда, но уже закрыт
    assert T.visible_at(fields, "2025-03-01") is False   # не правда и закрыт
    assert T.visible_at(fields, None) is False           # закрыт → не виден и без --as-of
    assert T.visible_at({"valid_from": "2024-01-01"}, None) is True


def test_temporal_of_ignores_absent_and_non_dict():
    assert T.temporal_of("строка") == {}
    assert T.temporal_of({"valid_from": None, "valid_to": "2024-01-01", "other": 1}) == {"valid_to": "2024-01-01"}


# --- выборки -----------------------------------------------------------------


def test_records_as_of_without_as_of_returns_everything():
    records = [_record("person:a"), _record("person:b", superseded_at="2024-01-01")]
    assert T.records_as_of(records, None) == records


def test_relations_as_of_filters_closed_edges():
    relations = [_rel("a", "b"), _rel("c", "d", superseded_at="2024-01-01")]
    assert T.relations_as_of(relations, None) == relations
    kept = T.relations_as_of(relations, "2024-06-01")
    assert [r["source_id"] for r in kept] == ["a"]


def test_query_records_as_of():
    records = [
        _record("person:a", valid_from="2024-01-01", valid_to="2024-06-30"),
        _record("person:b", valid_from="2024-06-30"),
        _record("person:c"),
    ]
    items, total, truncated = query_records(records, "person", None, 200, as_of="2024-06-30")
    assert truncated is False
    assert [r["record_id"] for r in items] == ["person:b", "person:c"]
    assert total == 2


# --- K40: point-in-time на засеянных интервалах ------------------------------


def test_k40_point_in_time_is_exact_on_seeded_intervals():
    """Точный ответ на каждом дне засеянного интервала, без допусков."""
    seeds = [
        ("person:a", "2024-01-01", "2024-03-01"),   # [янв, мар)
        ("person:b", "2024-02-01", "2024-04-01"),   # [фев, апр)
        ("person:c", "2024-03-15", None),           # [15 мар, ∞)
        ("person:d", None, "2024-02-15"),           # (-∞, 15 фев)
    ]
    records = [_record(rid, valid_from=start, valid_to=end) for rid, start, end in seeds]
    expected = {
        "2023-12-31": ["person:d"],
        "2024-01-01": ["person:a", "person:d"],
        "2024-02-14": ["person:a", "person:b", "person:d"],
        "2024-02-15": ["person:a", "person:b"],
        "2024-02-29": ["person:a", "person:b"],
        "2024-03-01": ["person:b"],
        "2024-03-14": ["person:b"],
        "2024-03-15": ["person:b", "person:c"],
        "2024-03-31": ["person:b", "person:c"],
        "2024-04-01": ["person:c"],
        "2025-01-01": ["person:c"],
    }
    for as_of, want in expected.items():
        items, total, _ = query_records(records, "person", None, 200, as_of=as_of)
        got = [r["record_id"] for r in items]
        assert got == want, f"на {as_of} ожидалось {want}, получено {got}"
        assert total == len(want)


def test_k40_interval_end_is_exclusive_not_inclusive():
    """Граница принадлежит прошлому: valid_to — это уже не правда."""
    records = [_record("person:a", valid_from="2024-01-01", valid_to="2024-02-01")]
    assert [r["record_id"] for r in query_records(records, "person", None, 200, as_of="2024-01-31")[0]] == ["person:a"]
    assert query_records(records, "person", None, 200, as_of="2024-02-01")[0] == []


# --- K41: инвалидация вместо удаления ---------------------------------------


def test_k41_contradicting_fact_closes_the_old_one(root):
    """Новый факт закрывает старый, старый остаётся читаемым."""
    old = _rel("company:x", "person:a", "employs",
               valid_from="2020-01-01", observed_at="2020-01-05T10:00:00Z",
               superseded_at="2024-06-01T09:00:00Z")
    new = _rel("company:x", "person:b", "employs",
               valid_from="2024-06-01", observed_at="2024-06-01T09:00:00Z")
    relations = [old, new]

    before = T.relations_as_of(relations, "2023-01-01")
    after = T.relations_as_of(relations, "2025-01-01")
    assert [r["target_id"] for r in before] == ["person:a"]
    assert [r["target_id"] for r in after] == ["person:b"]

    # Инвалидация, а не удаление: закрытый факт по-прежнему в данных и в ленте.
    assert old in relations
    entries = T.timeline(root, [], relations, limit=100)["entries"]
    facts = [e for e in entries if e["entry"] == "fact"]
    assert {e["target_id"] for e in facts} == {"person:a", "person:b"}
    closed = next(e for e in facts if e["target_id"] == "person:a")
    assert closed["superseded_at"] == "2024-06-01T09:00:00Z"


def test_k41_closed_fact_still_readable_through_records(root):
    """`records read` отдаёт закрытый факт: история не кэш, терять её нельзя."""
    path = root / "records" / "persons" / "a.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 1, "record_id": "person:a", "entity_type": "person",
        "valid_from": "2020-01-01", "superseded_at": "2024-06-01T09:00:00Z",
    }, indent=2) + "\n", encoding="utf-8")
    text = json.loads(path.read_text(encoding="utf-8"))
    assert text["superseded_at"] == "2024-06-01T09:00:00Z"
    assert T.records_as_of([_record("person:a", **{"superseded_at": "2024-06-01T09:00:00Z"})],
                           "2025-01-01") == []


# --- валидация ---------------------------------------------------------------


def test_validate_relations_reports_inverted_interval():
    records = [_record("a"), _record("b")]
    records[0]["data"]["relations"] = [
        {"type_id": "performed_by", "target": {"id": "b"}, "valid_from": "2024-06-01", "valid_to": "2024-01-01"},
    ]
    diags = validate_relations("d", records, {"performed_by"})
    assert [d.code for d in diags] == ["temporal.invalid_interval"]
    assert diags[0].location["pointer"] == "/relations/0/valid_to"


def test_validate_relations_reports_unparseable_instant():
    records = [_record("a"), _record("b")]
    records[0]["data"]["relations"] = [
        {"type_id": "performed_by", "target": {"id": "b"}, "valid_from": "прошлым летом"},
    ]
    diags = validate_relations("d", records, {"performed_by"})
    assert [d.code for d in diags] == ["temporal.invalid_instant"]
    assert diags[0].location["pointer"] == "/relations/0/valid_from"


def test_validate_relations_accepts_correct_intervals():
    records = [_record("a"), _record("b")]
    records[0]["data"]["relations"] = [
        {"type_id": "performed_by", "target": {"id": "b"},
         "valid_from": "2024-01-01", "valid_to": "2024-06-01", "observed_at": "2024-01-02T00:00:00Z"},
    ]
    assert validate_relations("d", records, {"performed_by"}) == []


# --- лента -------------------------------------------------------------------


def test_timeline_merges_events_and_facts_in_order(root):
    record_write(root, "notes/a.md", None, b"# A\n", kind="doc.create")
    facts = [_rel("company:x", "person:a", "employs", valid_from="2030-01-01")]
    result = T.timeline(root, [_record("company:x")], facts, limit=50)
    kinds = [(e["entry"], e.get("path")) for e in result["entries"]]
    assert ("event", "notes/a.md") in kinds
    assert ("fact", "records/company:x.json") in kinds
    assert result["count"] == 2 and result["truncated"] is False
    # Сортировка детерминирована: по времени, затем по виду и идентификатору.
    times = [e["at"] for e in result["entries"]]
    assert times == sorted(times)


def test_timeline_as_of_cuts_both_clocks(root):
    record_write(root, "notes/a.md", None, b"# A\n", kind="doc.create")
    facts = [_rel("company:x", "person:a", "employs", valid_from="2030-01-01")]
    result = T.timeline(root, [_record("company:x")], facts, as_of="2020-01-01", limit=50)
    assert result["as_of"] == "2020-01-01"
    assert result["entries"] == []


def test_timeline_path_filter_and_limit(root):
    record_write(root, "notes/a.md", None, b"# A\n", kind="doc.create")
    record_write(root, "notes/b.md", None, b"# B\n", kind="doc.create")
    result = T.timeline(root, [], [], path="notes/a.md", limit=10)
    assert [e["path"] for e in result["entries"]] == ["notes/a.md"]
    limited = T.timeline(root, [], [], limit=1)
    assert limited["truncated"] is True and len(limited["entries"]) == 1 and limited["count"] == 2


def test_timeline_skips_facts_without_interval_and_unknown_items(root):
    facts = [
        _rel("company:x", "person:a"),                       # нет темпоральных полей
        {"type_id": "employs", "source_id": "ghost", "target_id": "person:a"},  # владельца нет
    ]
    result = T.timeline(root, [_record("company:x")], facts, limit=10)
    assert result["entries"] == []


def test_timeline_rejects_unparseable_as_of(root):
    with pytest.raises(ValueError):
        T.timeline(root, [], [], as_of="вчера")


def test_timeline_ignores_non_dict_path_items(root):
    record_write(root, "notes/a.md", None, b"# A\n", kind="doc.create")
    from todoc.adapters.history import journal
    events = journal.read_events(root)
    events[0]["paths"].append("не словарь")
    journal_path = journal.journal_path(root)
    journal_path.write_text("\n".join(json.dumps({k: v for k, v in e.items() if k != "rev"},
                                                 ensure_ascii=False, sort_keys=True) for e in events) + "\n",
                            encoding="utf-8")
    result = T.timeline(root, [], [], limit=10)
    assert [e["path"] for e in result["entries"]] == ["notes/a.md"]
