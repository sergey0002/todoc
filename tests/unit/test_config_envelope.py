import json

import pytest

from todoc.config import init_dataset, load_dataset, load_rules
from todoc.errors import ValidationError
from todoc.output.envelope import emit, make_envelope
from todoc.typing_system.descriptors import TypeRegistry, load_json_file, require_schema_version


def test_init_creates_control_files(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    dataset = init_dataset(root)
    assert dataset["dataset_id"].startswith("dataset-")
    assert (root / ".todoc" / "dataset.json").is_file()
    assert (root / ".todoc" / "rules" / "directory-rules.json").is_file()
    assert (root / ".todoc" / "entity_types" / "workout" / "type.json").is_file()


def test_init_twice_fails(tmp_path):
    root = tmp_path / "kb"
    root.mkdir()
    init_dataset(root)
    with pytest.raises(ValidationError):
        init_dataset(root)


def test_load_dataset_missing(tmp_path):
    with pytest.raises(ValidationError):
        load_dataset(tmp_path)


def test_load_dataset_bad_version(root):
    path = root / ".todoc" / "dataset.json"
    path.write_text('{"schema_version": 2, "dataset_id": "x"}')
    with pytest.raises(ValidationError):
        load_dataset(root)


def test_load_dataset_missing_id(root):
    path = root / ".todoc" / "dataset.json"
    path.write_text('{"schema_version": 1}')
    with pytest.raises(ValidationError):
        load_dataset(root)


def test_load_rules(root):
    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    assert any(r["id"] == "reserved-plan" for r in dir_rules)
    assert any(r["id"] == "adr-markdown" for r in doc_rules)


def test_load_json_file_invalid(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{bad")
    with pytest.raises(ValidationError):
        load_json_file(path)


def test_require_schema_version_not_object(tmp_path):
    path = tmp_path / "x.json"
    path.write_text("[1]")
    with pytest.raises(ValidationError):
        require_schema_version(load_json_file(path), path)


def test_registry_load_and_validate(root):
    dataset = load_dataset(root)
    dir_rules, doc_rules = load_rules(root, dataset)
    registry = TypeRegistry()
    registry.load(root, dataset)
    registry.validate_references(dir_rules, doc_rules)
    assert "workout" in registry.entity_types
    assert "research" in registry.dir_types


def test_registry_unknown_type_ref(root):
    dataset = load_dataset(root)
    registry = TypeRegistry()
    registry.load(root, dataset)
    with pytest.raises(ValidationError):
        registry.validate_references([{"id": "r", "assign": {"dir_type": "ghost"}}], [])


def test_registry_duplicate_type(root):
    dataset = load_dataset(root)
    registry = TypeRegistry()
    registry.load(root, dataset)
    # Duplicate: load again into same store via _load_dir path is internal; simulate via direct insert check
    registry.entity_types["workout"] = {}
    with pytest.raises(ValidationError):
        registry._load_dir(root / ".todoc" / "entity_types", "entity_type", registry.entity_types)


def test_registry_missing_type_id(root, tmp_path):
    base = tmp_path / "types"
    (base / "bad").mkdir(parents=True)
    (base / "bad" / "type.json").write_text('{"schema_version": 1}')
    registry = TypeRegistry()
    with pytest.raises(ValidationError):
        registry._load_dir(base, "entity_type", registry.entity_types)


def test_envelope_json_stdout(capsys):
    emit(make_envelope(True, {"a": 1}), "json")
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["ok"] is True
    assert data["data"] == {"a": 1}
    assert data["schema_version"] == 1


def test_envelope_json_out_file(tmp_path):
    out = tmp_path / "report.json"
    emit(make_envelope(False, {}, [{"code": "x"}]), "json", str(out))
    assert json.loads(out.read_text())["ok"] is False


def test_envelope_table(capsys):
    emit(make_envelope(True, {"total": 3}, [], [{"argv": ["todoc", "x"], "purpose": "p"}]), "table")
    out = capsys.readouterr().out
    assert "ok: True" in out
    assert "total: 3" in out
    assert "next:" in out


def test_envelope_table_out_file(tmp_path):
    out = tmp_path / "report.txt"
    emit(make_envelope(True, {"a": 1}), "markdown", str(out))
    assert "ok: True" in out.read_text()


def test_init_dataset_accepts_an_explicit_id(tmp_path):
    """Явный идентификатор делает демо-датасет воспроизводимым (P2)."""
    dataset = init_dataset(tmp_path, "demo-fixed")
    assert dataset["dataset_id"] == "demo-fixed"
    assert load_dataset(tmp_path)["dataset_id"] == "demo-fixed"


def test_init_dataset_trims_and_rejects_an_empty_id(tmp_path):
    import pytest
    assert init_dataset(tmp_path, "  spaced  ")["dataset_id"] == "spaced"
    fresh = tmp_path / "other"
    fresh.mkdir()
    with pytest.raises(ValidationError) as exc:
        init_dataset(fresh, "   ")
    assert exc.value.code == "config.invalid_schema"


def test_init_dataset_default_id_stays_random(tmp_path):
    first = init_dataset(tmp_path)
    second_dir = tmp_path / "second"
    second_dir.mkdir()
    second = init_dataset(second_dir)
    assert first["dataset_id"].startswith("dataset-")
    assert first["dataset_id"] != second["dataset_id"]
