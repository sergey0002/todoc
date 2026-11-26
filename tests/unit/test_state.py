# tests/unit/test_state.py — Задача 1 плана agent-state: ядро хранилища стейта
import json
from pathlib import Path

import pytest

from todoc.application.state import (
    ALLOWED_KEYS_V1,
    get_var,
    load_state,
    set_var,
    state_path,
    unset_var,
)
from todoc.errors import ValidationError


@pytest.fixture(autouse=True)
def _xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))


def test_state_path_under_xdg():
    import os

    assert state_path("dataset-x") == Path(
        os.environ["XDG_STATE_HOME"]) / "todoc" / "state-dataset-x.json"


def test_default_path_without_xdg(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert state_path("d") == tmp_path / ".local/state/todoc/state-d.json"


def test_set_get_roundtrip(tmp_path):
    set_var("dataset-x", "context.current_project", "shop", now="2026-11-25T00:00:00Z")
    assert get_var("dataset-x", "context.current_project") == "shop"
    raw = json.loads((tmp_path / "state/todoc/state-dataset-x.json").read_text(encoding="utf-8"))
    assert raw == {"schema_version": 1, "vars": {"context.current_project": "shop"},
                   "updated_at": "2026-11-25T00:00:00Z"}


def test_missing_file_returns_empty(tmp_path):
    assert load_state("dataset-x") == {"schema_version": 1, "vars": {}, "updated_at": None}
    assert get_var("dataset-x", "context.current_project") is None


def test_unknown_key_rejected(tmp_path):
    with pytest.raises(ValidationError) as err:
        set_var("dataset-x", "foo.bar", "x")
    assert err.value.code == "state.unknown_key"
    assert ALLOWED_KEYS_V1 == ("context.current_project",)


def test_unknown_key_rejected_on_get_and_unset():
    with pytest.raises(ValidationError) as e1:
        get_var("dataset-x", "nope")
    with pytest.raises(ValidationError) as e2:
        unset_var("dataset-x", "nope")
    assert e1.value.code == e2.value.code == "state.unknown_key"


@pytest.mark.parametrize("bad", ["", "x" * 257, 123, None])
def test_invalid_value_rejected(bad):
    with pytest.raises(ValidationError) as err:
        set_var("dataset-x", "context.current_project", bad)
    assert err.value.code == "state.invalid_value"


def test_limit_exceeded_on_keys(tmp_path, monkeypatch):
    # счётчик хранимых vars: (0 хранимых + 1 новая) > лимита 0
    monkeypatch.setattr("todoc.application.state._MAX_KEYS", 0)
    with pytest.raises(ValidationError) as err:
        set_var("dataset-x", "context.current_project", "shop")
    assert err.value.code == "state.limit_exceeded"


def test_limit_exceeded_on_file_size(tmp_path, monkeypatch):
    monkeypatch.setattr("todoc.application.state._MAX_BYTES", 10)
    set_var("dataset-x", "context.current_project", "shop")  # файл уже больше 10 байт
    with pytest.raises(ValidationError) as err:
        set_var("dataset-x", "context.current_project", "shop2")
    assert err.value.code == "state.limit_exceeded"


def test_file_unavailable_on_read_only_dir(tmp_path):
    import os

    locked = tmp_path / "state/todoc"
    locked.mkdir(parents=True)
    (locked / "state-dataset-x.json").write_text("{}", encoding="utf-8")
    os.chmod(locked, 0o500)  # read-only каталог: mkstemp невозможен
    try:
        if os.getuid() == 0:  # root пишет поверх прав
            pytest.skip("chmod не блокирует root")
        with pytest.raises(ValidationError) as err:
            set_var("dataset-x", "context.current_project", "shop")
        assert err.value.code == "state.file_unavailable"
        assert "state-dataset-x.json" in str(err.value)
    finally:
        os.chmod(locked, 0o700)


def test_corrupted_file_reported(tmp_path):
    p = tmp_path / "state/todoc"
    p.mkdir(parents=True)
    (p / "state-dataset-x.json").write_text("не-json", encoding="utf-8")
    with pytest.raises(ValidationError) as err:
        load_state("dataset-x")
    assert err.value.code == "state.file_unavailable"


def test_corrupted_structure_reported(tmp_path):
    p = tmp_path / "state/todoc"
    p.mkdir(parents=True)
    (p / "state-dataset-x.json").write_text('{"schema_version": 1}', encoding="utf-8")
    with pytest.raises(ValidationError) as err:
        load_state("dataset-x")
    assert err.value.code == "state.file_unavailable"


def test_unset_removes_and_reports_absence(tmp_path):
    set_var("dataset-x", "context.current_project", "shop", now="2026-11-25T00:00:00Z")
    assert unset_var("dataset-x", "context.current_project") is True
    assert get_var("dataset-x", "context.current_project") is None
    assert unset_var("dataset-x", "context.current_project") is False  # уже нет
    assert get_var("dataset-x", "context.current_project") is None  # файл жив, vars пуст
