import pytest

from todoc.application.query import aggregate_records, graph_neighbors, query_records
from todoc.errors import ValidationError


def _records():
    return [
        {"record_id": "workout:1", "entity_type": "workout", "data": {"date": "2026-11-01", "volume": {"value": 10, "unit": "kg"}, "muscle": "triceps"}},
        {"record_id": "workout:2", "entity_type": "workout", "data": {"date": "2026-11-02", "volume": {"value": 20, "unit": "kg"}, "muscle": "biceps"}},
        {"record_id": "person:sergei", "entity_type": "person", "data": {"name": "Sergei"}},
    ]


def test_query_by_type():
    items, total, truncated = query_records(_records(), "workout")
    assert total == 2
    assert len(items) == 2
    assert truncated is False


def test_query_filter():
    items, total, _ = query_records(_records(), "workout", {"muscle": "triceps"})
    assert total == 1
    assert items[0]["record_id"] == "workout:1"


def test_query_filter_in():
    items, total, _ = query_records(_records(), "workout", {"muscle": {"$in": ["triceps", "biceps"]}})
    assert total == 2


def test_query_limit_truncated():
    items, total, truncated = query_records(_records(), "workout", limit=1)
    assert total == 2
    assert len(items) == 1
    assert truncated is True


def test_aggregate_sum():
    result = aggregate_records(_records(), "workout", "volume")
    assert result["groups"]["all"] == 30.0
    assert result["units"] == "kg"
    assert result["formula"] == "sum(volume)"
    assert sorted(result["incoming_ids"]) == ["workout:1", "workout:2"]
    assert result["completeness"] == "complete"


def test_aggregate_group_by():
    result = aggregate_records(_records(), "workout", "volume", "muscle")
    assert result["groups"] == {"triceps": 10.0, "biceps": 20.0}


def test_aggregate_no_records():
    with pytest.raises(ValidationError):
        aggregate_records([], "workout", "volume")


def test_aggregate_unknown_metric():
    with pytest.raises(ValidationError):
        aggregate_records(_records(), "workout", "missing")


def test_aggregate_unit_mismatch():
    records = [
        {"record_id": "w:1", "entity_type": "workout", "data": {"volume": {"value": 1, "unit": "kg"}}},
        {"record_id": "w:2", "entity_type": "workout", "data": {"volume": {"value": 1, "unit": "lb"}}},
    ]
    with pytest.raises(ValidationError):
        aggregate_records(records, "workout", "volume")


def test_aggregate_unit_mismatch_names_the_group():
    """A mismatch inside one group is refused, and the message says which group."""
    records = [
        {"record_id": "m:1", "entity_type": "metric",
         "data": {"aspect": "tests", "value": {"value": 1, "unit": "count"}}},
        {"record_id": "m:2", "entity_type": "metric",
         "data": {"aspect": "tests", "value": {"value": 2, "unit": "ms"}}},
    ]
    with pytest.raises(ValidationError) as exc:
        aggregate_records(records, "metric", "value", "aspect")
    assert exc.value.code == "query.unit_mismatch"
    assert "tests" in exc.value.message and "count" in exc.value.message


def test_aggregate_mixed_units_across_groups_is_allowed():
    """Different groups may carry different units; each group reports its own."""
    records = [
        {"record_id": "m:1", "entity_type": "metric",
         "data": {"aspect": "tests", "value": {"value": 300, "unit": "count"}}},
        {"record_id": "m:2", "entity_type": "metric",
         "data": {"aspect": "tests", "value": {"value": 27, "unit": "count"}}},
        {"record_id": "m:3", "entity_type": "metric",
         "data": {"aspect": "performance", "value": {"value": 1500, "unit": "ms"}}},
        {"record_id": "m:4", "entity_type": "metric",
         "data": {"aspect": "benchmark", "value": {"value": 0.94, "unit": "ratio"}}},
    ]
    result = aggregate_records(records, "metric", "value", "aspect")
    assert result["groups"] == {"tests": 327.0, "performance": 1500.0, "benchmark": 0.94}
    assert result["group_units"] == {"tests": "count", "performance": "ms", "benchmark": "ratio"}
    # no single unit describes the whole result
    assert result["units"] == ""


def test_aggregate_plain_number():
    records = [{"record_id": "w:1", "entity_type": "workout", "data": {"reps": 5}}]
    result = aggregate_records(records, "workout", "reps")
    assert result["groups"]["all"] == 5.0


def test_graph_neighbors():
    relations = [
        {"type_id": "performed_by", "source_id": "workout:1", "target_id": "person:sergei"},
        {"type_id": "performed_by", "source_id": "workout:2", "target_id": "person:sergei"},
    ]
    edges = graph_neighbors(relations, "person:sergei", "performed_by", depth=1, limit=10)
    assert len(edges) == 2
    edges2 = graph_neighbors(relations, "workout:1", None, depth=2, limit=10)
    assert any(e["to"] == "person:sergei" for e in edges2)
    assert graph_neighbors(relations, "unknown", None, depth=1, limit=10) == []


def test_aggregate_carries_the_declared_prompt():
    """metric_fields.<f> объявляет промпт; он доходит до ответа неизменным (P1-11)."""
    spec = {"unit": "kg", "prompt": "Суммарный тоннаж за тренировку."}
    result = aggregate_records(_records(), "workout", "volume", metric_spec=spec)
    assert result["prompt"] == "Суммарный тоннаж за тренировку."
    assert result["formula"] == "sum(volume)"
    assert result["groups"]["all"] == 30.0


def test_aggregate_without_a_declared_metric_has_an_empty_prompt():
    result = aggregate_records(_records(), "workout", "volume")
    assert result["prompt"] == ""


def test_aggregate_ignores_a_malformed_metric_spec():
    """Не-словарь вместо описателя не роняет агрегацию: промпт просто пуст."""
    result = aggregate_records(_records(), "workout", "volume", metric_spec="не словарь")
    assert result["prompt"] == ""
    assert result["groups"]["all"] == 30.0



@pytest.mark.parametrize("value", [True, 10 ** 400, float("inf"), {"value": "2", "unit": "g"}])
def test_aggregate_refuses_nonfinite_and_nonnumeric_values(value):
    record = {"entity_type": "metric", "record_id": "metric:a", "data": {"value": value}}
    with pytest.raises(ValidationError) as error:
        aggregate_records([record], "metric", "value")
    assert error.value.code == "query.unknown_metric"


def test_aggregate_refuses_overflowing_group_sum():
    records = [{"entity_type": "metric", "record_id": f"metric:{i}", "data": {"value": 1e308}}
               for i in range(2)]
    with pytest.raises(ValidationError) as error:
        aggregate_records(records, "metric", "value")
    assert error.value.code == "query.aggregate_overflow"
