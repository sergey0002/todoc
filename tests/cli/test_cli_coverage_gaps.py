# tests/cli/test_cli_coverage_gaps.py — закрытие ветвей, оставшихся из волн
# entity-catalog/skills-vault (гейт CI — 100% покрытия; см. docs/state/10).
import json
import pathlib
import sys
import contextlib
from pathlib import Path

import pytest
from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError

from test_cli_interop import _init_interop, _run


def _init_min(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--apply", "--root", str(tmp_path), "--no-input"]).exit_code == 0
    return runner


def _skill_md(name="demo", desc="Описание скила"):
    return f"---\nname: {name}\ndescription: {desc}\n---\n\n# {name}\n\nТело скила.\n"


def test_skills_tree_without_vault(tmp_path):
    runner = _init_min(tmp_path)
    r = _run(runner, ["skills", "tree", "--root", str(tmp_path)])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "skills.not_found"


def test_skills_tree_warns_above_500(tmp_path):
    runner = _init_min(tmp_path)
    vault = tmp_path / "skills"
    for i in range(501):
        d = vault / f"bulk/skill-{i:03d}"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(_skill_md(f"skill-{i:03d}"), encoding="utf-8")
    r = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--limit", "5"])
    assert r.exit_code == 0, r.output


def test_skills_read_budget_truncates(tmp_path):
    runner = _init_min(tmp_path)
    d = tmp_path / "skills" / "big"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(_skill_md() + "X" * 2000 + "\n", encoding="utf-8")
    r = _run(runner, ["skills", "read", "--root", str(tmp_path), "--path", "big", "--budget", "50"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)["data"]["result"]
    assert data["truncated"] is True
    assert len(data["content"]) == 50
    assert len(data["content"].encode("utf-8")) > 50
    r2 = _run(runner, ["skills", "read", "--root", str(tmp_path), "--path", "big", "--budget", "100000"])
    assert r2.exit_code == 0, r2.output
    assert json.loads(r2.output)["data"]["result"]["truncated"] is False  # бюджет не достигнут


def test_skills_attach_requires_root(tmp_path):
    runner = CliRunner()
    dest = tmp_path / "platform"
    r = _run(runner, ["skills", "attach", "--apply", "--to", str(dest)])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "usage.error"


def test_skills_attach_copies_subdirs_and_assets(tmp_path, monkeypatch):
    # files("todoc") возвращает КОРЕНЬ пакета; cli достраивает data/agent-skill/todoc.
    # Подкаталог → continue, не-SKILL.md → write_bytes.
    root = tmp_path / "pkg"
    pkg = root / "data" / "agent-skill" / "todoc"
    (pkg / "references").mkdir(parents=True)
    (pkg / "SKILL.md").write_text("Руководство {ROOT}\n", encoding="utf-8")
    (pkg / "references" / "workflow.md").write_text("workflow\n", encoding="utf-8")
    (pkg / "asset.bin").write_bytes(b"\x00\x01\x02")

    import importlib.resources as real_resources

    @contextlib.contextmanager
    def fake_as_file(pkg_path):
        yield Path(pkg_path)

    monkeypatch.setattr(real_resources, "files", lambda name: root)
    monkeypatch.setattr(real_resources, "as_file", fake_as_file)

    runner = CliRunner()
    proj = tmp_path / "proj" / ".agents" / "skills"
    proj.mkdir(parents=True)
    demo = tmp_path / "demo"
    demo.mkdir()
    r = _run(runner, ["skills", "attach", "--apply", "--to", str(proj), "--root", str(demo)])
    assert r.exit_code == 0, r.output
    installed = proj / "todoc"
    assert (installed / "SKILL.md").read_text(encoding="utf-8") == "Руководство " + str(demo) + "\n"
    assert (installed / "references" / "workflow.md").exists()      # каталог пропущен, файл скопирован
    assert (installed / "asset.bin").read_bytes() == b"\x00\x01\x02"


def test_skills_import_missing_source_and_no_skill_md(tmp_path):
    runner = _init_min(tmp_path)
    (tmp_path / "skills").mkdir()
    r = _run(runner, ["skills", "import", "--apply", "--root", str(tmp_path),
                      "--src", str(tmp_path / "missing"), "--into", "x"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "skills.not_found"
    empty = tmp_path / "empty-src"
    empty.mkdir()
    r = _run(runner, ["skills", "import", "--apply", "--root", str(tmp_path),
                      "--src", str(empty), "--into", "x"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "skills.not_found"


def test_docs_links_edge_cases(tmp_path, monkeypatch):
    runner = _init_min(tmp_path)
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "a.md").write_text(
        "---\nid: doc:a\ntitle: A\n---\n\n[[ok]] и [[missing]]\n", encoding="utf-8")
    (notes / "ok.md").write_text("---\nid: doc:ok\ntitle: OK\n---\n\nТело.\n", encoding="utf-8")
    (notes / "tab.csv").write_text("col\n1\n", encoding="utf-8")  # не-markdown: continue
    broken = notes / "broken.md"
    broken.write_text("---\nid: doc:b\n---\n\nтекст\n", encoding="utf-8")
    # wikilink с пустой целью — защитная ветка: подсунем линк парсером
    import todoc.cli as cli_mod
    from todoc.adapters.formats.markdown import parse_markdown as real_parse
    from types import SimpleNamespace

    def parse_with_empty_wikilink(text):
        doc = real_parse(text)
        if "id: doc:a" in text:
            doc.links.append(SimpleNamespace(target="", is_wikilink=True))
        return doc

    monkeypatch.setattr(cli_mod, "parse_markdown", parse_with_empty_wikilink)
    r = _run(runner, ["docs", "links", "--root", str(tmp_path)])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)["data"]
    assert data["meta"]["total_links"] == 2
    assert data["meta"]["total"] == 1
    broken.write_bytes(b"\xff")
    incomplete = _run(runner, ["docs", "links", "--root", str(tmp_path)])
    assert incomplete.exit_code == 6
    body = json.loads(incomplete.output)
    assert body["diagnostics"][0]["path"] == "notes/broken.md"
    assert body["data"]["meta"]["complete"] is False


def test_flow_render_overwrite_and_missing_pointer(tmp_path):
    runner = _init_interop(tmp_path)
    flow_path = tmp_path / "records" / "flows" / "checkout.json"
    rec = json.loads(flow_path.read_text(encoding="utf-8"))
    rec.pop("outcomes")  # один из якорных поинтеров не разрешается — ветка skip
    flow_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _run(runner, ["index", "rebuild", "--apply", "--root", str(tmp_path)])
    args = ["interop", "export", "--root", str(tmp_path)]  # noqa: F841 (маркер файла)
    from todoc.cli import cli as _cli  # noqa: F401
    r = _run(runner, ["docs", "flow", "render", "--apply", "--root", str(tmp_path),
                      "--id", "flow:checkout", "--write", "exports/view.md"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)["data"]["result"]
    assert data["derived_from"] == 2  # /outcomes отсутствует (и /relations в фикстуре нет)
    r2 = _run(runner, ["docs", "flow", "render", "--apply", "--root", str(tmp_path),
                       "--id", "flow:checkout", "--write", "exports/view.md"])
    assert r2.exit_code == 0, r2.output  # перезапись derived-цели поверх CAS


def test_docs_status_without_front_matter(tmp_path):
    runner = _init_min(tmp_path)
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "plain.md").write_text("Просто текст без front matter.\n", encoding="utf-8")
    r = _run(runner, ["docs", "status", "--apply", "--root", str(tmp_path), "--id", "doc:notes/plain.md",
                      "--set", "open"])
    assert r.exit_code != 0
    assert getattr(r.exception, "code", "") == "docs.no_status_field"


def test_docs_status_without_updated_bumps_nothing(tmp_path):
    runner = _init_min(tmp_path)
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "s.md").write_text(
        "---\nid: doc:s\ntitle: S\ndoc_type: note\nstatus: draft\n---\n\nТело.\n", encoding="utf-8")
    r = _run(runner, ["docs", "status", "--apply", "--root", str(tmp_path), "--id", "doc:s", "--set", "open"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["data"]["result"]["status"] == "open"
    text = (notes / "s.md").read_text(encoding="utf-8")
    assert "status: open" in text and "updated:" not in text


def test_apply_edit_ops_delete_range_and_fm_variants(tmp_path):
    import datetime as dt
    from todoc.application.write import apply_edit_ops
    from todoc.errors import ValidationError

    f = tmp_path / "doc.md"
    f.write_text("---\ntitle: T\n---\n\nстрока1\nстрока2\nстрока3\n", encoding="utf-8")
    # fm без updated: бампа нет (ветка), delete одной строки валиден
    new_hash, bumped = apply_edit_ops(tmp_path, "doc.md",
                                      [{"op": "delete", "line": 6, "to": 6}], bump_updated=True)
    assert bumped is False
    text = f.read_text(encoding="utf-8")
    assert "строка1" in text and "строка3" in text and "строка2" not in text
    # fm с updated == сегодня: бампа нет (вторая ветка)
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    g = tmp_path / "today.md"
    g.write_text(f"---\ntitle: T\nupdated: {today}\n---\n\nтело\n", encoding="utf-8")
    _h, bumped2 = apply_edit_ops(tmp_path, "today.md", [{"op": "replace", "line": 5, "text": "новое"}],
                                 bump_updated=True)
    assert bumped2 is False
    # без front matter: цикл бампа завершается без break
    h = tmp_path / "nofm.md"
    h.write_text("просто тело\nи ещё строка\n", encoding="utf-8")
    _h, bumped3 = apply_edit_ops(tmp_path, "nofm.md", [{"op": "replace", "line": 1, "text": "новое"}],
                                 bump_updated=True)
    assert bumped3 is False
    # fm без закрывающего "---": цикл бампа до конца списка без break
    k = tmp_path / "unclosed.md"
    k.write_text("---\ntitle: T\n\nтело без закрывающего\n", encoding="utf-8")
    _h, bumped4 = apply_edit_ops(tmp_path, "unclosed.md", [{"op": "replace", "line": 4, "text": "новое"}],
                                 bump_updated=True)
    assert bumped4 is False
    # delete: end за пределами файла
    with pytest.raises(ValidationError) as exc:
        apply_edit_ops(tmp_path, "doc.md", [{"op": "delete", "line": 1, "to": 99}], bump_updated=True)
    assert exc.value.code == "edit.line_out_of_range"
