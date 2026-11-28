"""Contract tests for tools/refresh_demo_state.py (BUG-059)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import refresh_demo_state as refresh  # noqa: E402


@pytest.fixture()
def layout(tmp_path, monkeypatch):
    src = tmp_path / "docs" / "state"
    dst = tmp_path / "demo" / "references" / "state"
    src.mkdir(parents=True)
    dst.mkdir(parents=True)
    monkeypatch.setattr(refresh, "SRC", src)
    monkeypatch.setattr(refresh, "DST", dst)
    return src, dst


def _copy(dst: Path, name: str, created: str = "2026-11-24", updated: str = "2026-11-27") -> Path:
    target = dst / name
    target.write_text(
        f"---\ncreated: {created}\nupdated: {updated}\nid: doc:state-{name[:-3]}\n"
        f'title: "Состояние"\ndoc_type: reference\nlang: ru\n'
        f"source: docs/state/{name}\ncopied: true\n---\n\n# Old\n",
        encoding="utf-8",
    )
    return target


def test_generated_cli_md_does_not_block_refresh(layout, capsys):
    src, dst = layout
    (src / "cli.md").write_text("# generated\n", encoding="utf-8")
    (src / "01-a.md").write_text("# A\n", encoding="utf-8")
    _copy(dst, "01-a.md")
    assert refresh.main([]) == 0
    assert "refreshed 1 of 1" in capsys.readouterr().out


def test_dates_and_second_run_are_stable(layout):
    src, dst = layout
    (src / "01-a.md").write_text("# A\n", encoding="utf-8")
    target = _copy(dst, "01-a.md")
    assert refresh.main([]) == 0
    first = target.read_bytes()
    assert b"created: 2026-11-24" in first
    assert b"updated: 2026-11-27" in first
    assert refresh.main([]) == 0
    assert target.read_bytes() == first


def test_link_remap_delink_and_after_plan(layout):
    src, dst = layout
    (dst.parents[1] / "ideas").mkdir(parents=True, exist_ok=True)
    (src / "01-a.md").write_text(
        "[asset](../../demo/README.md) [repo](../README.md) "
        "[after](../plan/foo.after.md) [plan](../plan/constitution.md) "
        "[cli](cli.md) [code](../../src/todoc/cli.py) [guide](../guides/python-api-for-agents.md) "
        "[folder](../../demo/ideas) [schema](../../demo/.todoc/document-metadata.schema.json)\n",
        encoding="utf-8")
    target = _copy(dst, "01-a.md")
    assert refresh.main([]) == 0
    body = target.read_text(encoding="utf-8")
    assert "[asset](../../README.md)" in body
    assert "[repo](../README.md)" not in body and "repo" in body
    assert "[after](../../plan/after/foo.after.md)" in body
    assert "[plan](../../plan/constitution.md)" in body
    assert "[cli](cli.md)" not in body and "cli" in body
    assert "](../../src/" not in body and "code" in body
    assert "](../guides/" not in body and "guide" in body
    assert "[folder]" not in body and "folder" in body
    assert "[schema]" not in body and "schema" in body


def test_missing_copy_still_fails(layout, capsys):
    src, dst = layout
    (src / "01-a.md").write_text("# A\n", encoding="utf-8")
    assert refresh.main([]) == 1
    assert "no demo copy" in capsys.readouterr().err


def test_copy_without_front_matter_is_reported(layout, capsys):
    src, dst = layout
    (src / "01-a.md").write_text("# A\n", encoding="utf-8")
    (dst / "01-a.md").write_text("# no front matter\n", encoding="utf-8")
    assert refresh.main([]) == 1
    assert "no front matter" in capsys.readouterr().err


def test_check_reports_drift_without_writing(layout, capsys):
    src, dst = layout
    (src / "01-a.md").write_text("# New body\n", encoding="utf-8")
    target = _copy(dst, "01-a.md")
    before = target.read_bytes()
    assert refresh.main(["--check"]) == 1
    assert "stale" in capsys.readouterr().out
    assert target.read_bytes() == before
    assert refresh.main([]) == 0
    assert refresh.main(["--check"]) == 0
    assert "up to date" in capsys.readouterr().out
