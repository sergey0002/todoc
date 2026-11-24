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
