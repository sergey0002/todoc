import json
from pathlib import Path

from todoc.application.validator import validate_dataset


def _cfg(root: Path, rel: str, body: str) -> None:
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / ".config.json").write_text(body, encoding="utf-8")


def test_validate_dataset_merges_folder_configs(tmp_path):
    (tmp_path / ".todoc").mkdir()
    (tmp_path / ".todoc" / "dataset.json").write_text(
        json.dumps({"dataset_id": "ds-fc-test"}), encoding="utf-8")
    dataset = {"dataset_id": "ds-fc-test"}
    _cfg(tmp_path, "notes", '{"schema_version": 1, "title": "Заметки", "color": "red"}')
    diags, _ = validate_dataset(tmp_path, dataset, [], [], [], None)
    assert {d.code for d in diags} == {"folder.config.unknown_field"}
    assert all(d.dataset_id == "ds-fc-test" for d in diags)
    assert diags[0].path == "notes/.config.json"
    # без конфигов — ноль диагностик
    import shutil
    shutil.rmtree(tmp_path / "notes")
    diags2, _ = validate_dataset(tmp_path, dataset, [], [], [], None)
    assert diags2 == []
