from __future__ import annotations

import subprocess
from pathlib import Path
import pytest

from todoc.adapters.filesystem.scanner import file_hash
from todoc.application.sync import detect_dirty_paths, normalize_sync_path, sync_files
from todoc.config import init_dataset
from todoc.errors import AccessError, ConflictError, ValidationError
from todoc.output.envelope import emit, make_envelope
from todoc.service import DatasetContext


def _init_git_kb(tmp_path: Path) -> tuple[Path, Path]:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    kb = tmp_path / "demo"
    init_dataset(kb)
    exp_dir = kb / ".todoc" / "doc_types" / "export"
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "type.json").write_text(
        '{"schema_version": 1, "type_id": "export", "version": "1.0", "kind": "doc_type", '
        '"description": "Generated export", "format": "markdown", "generated": true}\n',
        encoding="utf-8",
    )
    (kb / "notes").mkdir(parents=True, exist_ok=True)
    (kb / "exports").mkdir(parents=True, exist_ok=True)
    (kb / "plan").mkdir(parents=True, exist_ok=True)
    (kb / "records").mkdir(parents=True, exist_ok=True)
    (kb / "notes" / "hello.md").write_text(
        "---\nid: doc:notes/hello.md\ntitle: Привет\ndoc_type: note\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n# Привет\n\n## Суть\n\nТекст v1.\n",
        encoding="utf-8",
    )
    (kb / "exports" / "view.md").write_text(
        '---\nid: doc:exports/view.md\ntitle: Экспорт\ndoc_type: export\nderived_from: ["notes/hello.md@sha256:111"]\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n# Экспорт\n\nv1\n',
        encoding="utf-8",
    )
    (kb / "plan" / "p1.md").write_text(
        '---\nid: doc:plan/p1.md\ntitle: План\ndoc_type: note\nderived_from: ["notes/hello.md@sha256:111"]\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n# План\n\n## Суть\n\nШаг 1\n',
        encoding="utf-8",
    )
    ctx = DatasetContext(kb)
    ctx.rebuild_index(force=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path, kb


def test_normalize_sync_path_accepts_root_relative_cwd_relative_and_guards_bounds(tmp_path: Path) -> None:
    repo, kb = _init_git_kb(tmp_path)
    assert normalize_sync_path(kb, "notes/hello.md", cwd=repo) == "notes/hello.md"
    assert normalize_sync_path(kb, "demo/notes/hello.md", cwd=repo) == "notes/hello.md"
    assert normalize_sync_path(kb, str(kb / "notes" / "hello.md")) == "notes/hello.md"
    with pytest.raises(AccessError):
        normalize_sync_path(kb, "../outside.md", cwd=kb)
    with pytest.raises(AccessError):
        normalize_sync_path(kb, "/etc/passwd", cwd=kb)
    with pytest.raises(ValidationError):
        normalize_sync_path(kb, ".todoc/dataset.json", cwd=kb)
    with pytest.raises(ValidationError):
        normalize_sync_path(kb, "", cwd=kb)
    with pytest.raises(ValidationError):
        normalize_sync_path(kb, ".", cwd=kb)


def test_sync_files_bumps_updated_records_ranges_and_is_idempotent(tmp_path: Path) -> None:
    repo, kb = _init_git_kb(tmp_path)
    note = kb / "notes" / "hello.md"
    note.write_text(note.read_text(encoding="utf-8").replace("Текст v1.", "Текст v2."), encoding="utf-8")

    ctx = DatasetContext(kb)
    res = sync_files(ctx, ["demo/notes/hello.md"], cwd=repo)
    assert res["ok"] is True
    assert res["diagnostics"] == []
    assert res["guidance"] is None
    assert res["synced"][0]["path"] == "notes/hello.md"
    assert res["synced"][0]["status"] == "synced"
    assert res["synced"][0]["updated_bumped"] is True
    assert "updated: 2026-01-01" not in note.read_text(encoding="utf-8")

    res2 = sync_files(ctx, ["notes/hello.md"], cwd=repo)
    assert res2["synced"][0]["status"] == "unchanged"
    assert res2["synced"][0]["updated_bumped"] is False


def test_sync_blocks_generated_views_unless_allow_derived_and_allows_plan_with_derived_from(tmp_path: Path) -> None:
    repo, kb = _init_git_kb(tmp_path)
    exp = kb / "exports" / "view.md"
    exp.write_text(exp.read_text(encoding="utf-8").replace("v1", "ручная правка"), encoding="utf-8")
    plan = kb / "plan" / "p1.md"
    plan.write_text(
        plan.read_text(encoding="utf-8").replace("Шаг 1", "Шаг 1 выполнен (проверка `<!-- СГЕНЕРИРОВАНО:`)"),
        encoding="utf-8",
    )

    fm_gen = kb / "notes" / "fm-gen.md"
    fm_gen.write_text(
        '---\nid: doc:notes/fm-gen.md\ntitle: Gen\ndoc_type: note\ngenerated: true\nderived_from: ["notes/hello.md"]\n---\n\n# Gen\n\n## Суть\n\nv1\n',
        encoding="utf-8",
    )
    marker_gen = kb / "notes" / "marker-gen.md"
    marker_gen.write_text(
        "---\nid: doc:notes/marker-gen.md\ntitle: MGen\ndoc_type: note\n---\n\n<!-- СГЕНЕРИРОВАНО: flow render -->\n\n# MGen\n\n## Суть\n\nv1\n",
        encoding="utf-8",
    )
    ctx = DatasetContext(kb)
    res_plan = sync_files(ctx, ["plan/p1.md"], cwd=repo)
    assert res_plan["ok"] is True
    assert res_plan["synced"][0]["updated_bumped"] is True

    res_exp = sync_files(ctx, ["exports/view.md"], cwd=repo)
    assert res_exp["ok"] is False
    assert any(d["code"] == "docs.derived_edited_directly" for d in res_exp["diagnostics"])
    assert res_exp["guidance"] is not None
    assert res_exp["guidance"]["code"] == "sync.derived_view_blocked"
    assert "notes/hello.md@sha256:111" in res_exp["guidance"]["sources"]

    fm_gen.write_text(fm_gen.read_text(encoding="utf-8").replace("v1", "v2"), encoding="utf-8")
    res_fm_gen = sync_files(ctx, ["notes/fm-gen.md"], cwd=repo)
    assert res_fm_gen["ok"] is False
    assert "notes/hello.md" in res_fm_gen["guidance"]["sources"]

    marker_gen.write_text(marker_gen.read_text(encoding="utf-8").replace("v1", "v2"), encoding="utf-8")
    res_marker_gen = sync_files(ctx, ["notes/marker-gen.md"], cwd=repo)
    assert res_marker_gen["ok"] is False

    res_allow = sync_files(ctx, ["exports/view.md"], allow_derived=True, cwd=repo)
    assert res_allow["ok"] is True


def test_sync_dirty_mode_json_record_validation_error_deleted_file_if_hash_and_no_history(tmp_path: Path) -> None:
    repo, kb = _init_git_kb(tmp_path)
    note = kb / "notes" / "hello.md"
    old_hash = file_hash(note)
    note.write_text(note.read_text(encoding="utf-8").replace("Текст v1.", "Текст v3."), encoding="utf-8")

    # JSON-файл с синтаксической ошибкой для проверки guidance "sync.validation_failed"
    rec = kb / "records" / "r1.json"
    rec.write_text('{"schema_version": 1, broken_json\n', encoding="utf-8")

    ctx = DatasetContext(kb)
    dirty = detect_dirty_paths(ctx)
    assert "notes/hello.md" in dirty and "records/r1.json" in dirty

    with pytest.raises(ValidationError):
        sync_files(ctx, ["notes/hello.md", "plan/p1.md"], expected_hash=old_hash, cwd=repo)
    with pytest.raises(ConflictError):
        sync_files(ctx, ["notes/hello.md"], expected_hash="sha256:deadbeef", cwd=repo)

    # Старый хеш до прямой правки И текущий хеш на диске оба принимаются
    res_ok = sync_files(ctx, ["notes/hello.md"], expected_hash=old_hash, record_history=False, cwd=repo)
    assert res_ok["ok"] is True
    current_hash = file_hash(note)
    res_same_hash = sync_files(ctx, ["notes/hello.md"], expected_hash=current_hash, record_history=False, cwd=repo)
    assert res_same_hash["ok"] is True

    # JSON с ошибкой валидации даёт ok=False и guidance="sync.validation_failed"
    rec.write_text('{"schema_version": 1, still_broken_json\n', encoding="utf-8")
    res_bad = sync_files(ctx, ["records/r1.json"], record_history=True, cwd=repo)
    assert res_bad["ok"] is False
    assert res_bad["guidance"] is not None
    assert res_bad["guidance"]["code"] == "sync.validation_failed"

    # Удаляем сломанный JSON (проверяем --if-hash mismatch на удалённом файле и record_history=False) и p1.md
    rec.unlink()
    with pytest.raises(ConflictError):
        sync_files(ctx, ["records/r1.json"], expected_hash="sha256:wrong", record_history=False, cwd=repo)
    res_del_no_hist = sync_files(ctx, ["records/r1.json"], record_history=False, cwd=repo)
    assert res_del_no_hist["synced"][0]["status"] == "deleted"

    (kb / "plan" / "p1.md").unlink()
    # Вызов ensure_index создаёт событие external.change в журнале, которое _previous_hash_and_bytes пропускает
    ctx.ensure_index()
    res_del = sync_files(ctx, ["plan/p1.md"], record_history=True, cwd=repo)
    assert any(item["path"] == "plan/p1.md" and item["status"] == "deleted" for item in res_del["synced"])

    # Второй вызов dirty когда ничего не изменилось -> пустой список synced, ok=True
    res_clean = sync_files(ctx, (), dirty=True, record_history=False, cwd=repo)
    assert res_clean["ok"] is True
    assert res_clean["synced"] == []


def test_sync_on_embedded_backend_with_snapshot_in_journal(tmp_path: Path) -> None:
    kb = tmp_path / "vault"
    init_dataset(kb)
    (kb / "notes").mkdir(parents=True, exist_ok=True)
    doc = kb / "notes" / "n.md"
    doc.write_text("# N\n\n## Суть\n\nv1\n", encoding="utf-8")
    ctx = DatasetContext(kb)
    res1 = sync_files(ctx, ["notes/n.md"])
    assert res1["ok"] is True
    doc.write_text("# N\n\n## Суть\n\nv2\n", encoding="utf-8")
    res2 = sync_files(ctx, ["notes/n.md"])
    assert res2["ok"] is True
    assert res2["synced"][0]["status"] == "synced"


def test_envelope_guidance_backward_compatible_and_table_and_out_emit(tmp_path: Path, capsys) -> None:
    plain = make_envelope(True, {"a": 1})
    assert "guidance" not in plain.to_dict()

    with_null = make_envelope(True, {"a": 1}, include_guidance=True)
    assert "guidance" in with_null.to_dict() and with_null.to_dict()["guidance"] is None

    with_obj = make_envelope(
        False,
        {"a": 1},
        diagnostics=[{"severity": "error", "code": "c", "path": "p", "message": "m"}],
        next_actions=[{"argv": ["todoc", "sync"], "purpose": "retry"}],
        guidance={"code": "x", "summary": "fix it"},
        include_guidance=True,
    )
    emit(with_obj, "json")
    assert '"guidance"' in capsys.readouterr().out

    emit(with_obj, "table")
    out = capsys.readouterr().out
    assert "guidance:" in out

    table_file = tmp_path / "env.txt"
    emit(plain, "table", str(table_file))
    assert "guidance:" not in table_file.read_text(encoding="utf-8")

    out_file = tmp_path / "env.json"
    emit(with_obj, "json", str(out_file))
    assert '"guidance"' in out_file.read_text(encoding="utf-8")
