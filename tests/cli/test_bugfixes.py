# tests/cli/test_bugfixes.py — регресс-тесты исправлений BUG-001..010 (исполнение репортов)
import json

from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


def _init(tmp_path):
    runner = CliRunner()
    assert _run(runner, ["init", "--root", str(tmp_path)]).exit_code == 0


def _skill(root, rel, name, body):
    d = root / "skills" / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {name} скил.\n---\n\n{body}\n", encoding="utf-8")


# --- BUG-005: docs read --section учитывает --budget ---------------------------------

def test_section_budget_extends_window(tmp_path):
    _init(tmp_path)
    lines = "\n".join(f"строка {i} контента" for i in range(1, 61))
    (tmp_path / "inbox").mkdir()
    (tmp_path / "inbox/long.md").write_text(
        '---\ntitle: "Длинная"\n---\n\n# Длинная\n\n## Секция\n\n' + lines + "\n", encoding="utf-8")
    runner = CliRunner()
    r = _run(runner, ["docs", "read", "--root", str(tmp_path), "--id", "doc:inbox/long.md",
                      "--section", "Секция", "--budget", "12000"])
    d = _json(r)["data"]
    assert len(d["lines"]) == 62  # заголовок + пустая + 60 строк: лимит 40 снят бюджетом
    assert d["truncated"] is False
    assert d["section_total_lines"] == 62


def test_section_budget_small_cuts_early(tmp_path):
    _init(tmp_path)
    lines = "\n".join(f"строка {i} контента" for i in range(1, 61))
    (tmp_path / "inbox").mkdir()
    (tmp_path / "inbox/long.md").write_text(
        '---\ntitle: "Длинная"\n---\n\n# Длинная\n\n## Секция\n\n' + lines + "\n", encoding="utf-8")
    runner = CliRunner()
    r = _run(runner, ["docs", "read", "--root", str(tmp_path), "--id", "doc:inbox/long.md",
                      "--section", "Секция", "--budget", "150"])
    d = _json(r)["data"]
    assert len(d["lines"]) < 62 and len(d["lines"]) >= 1
    assert sum(len(ln.encode("utf-8")) + 1 for ln in d["lines"]) <= 150
    assert d["truncated"] is True
    assert d["section_total_lines"] == 62


# --- BUG-006: docs new транслитерирует кириллический заголовок -----------------------

def test_docs_new_transliterates_cyrillic_title(tmp_path):
    _init(tmp_path)
    runner = CliRunner()
    r = _run(runner, ["docs", "new", "--root", str(tmp_path), "--title", "Оформление заказа",
                      "--dir", "inbox", "--template", "note"])
    d = _json(r)["data"]
    assert d["path"] == "inbox/oformlenie-zakaza.md"
    assert (tmp_path / "inbox/oformlenie-zakaza.md").is_file()
    assert "Оформление заказа" in (tmp_path / "inbox/oformlenie-zakaza.md").read_text(encoding="utf-8")


def test_docs_new_punctuation_only_title_falls_back(tmp_path):
    _init(tmp_path)
    runner = CliRunner()
    r = _run(runner, ["docs", "new", "--root", str(tmp_path), "--title", "!!!",
                      "--dir", "inbox", "--template", "note"])
    assert _json(r)["data"]["path"] == "inbox/untitled.md"


# --- BUG-008: skills tree — каскадный счётчик раздела --------------------------------

def test_skills_tree_section_counts_include_descendants(tmp_path):
    _init(tmp_path)
    _skill(tmp_path, "coding/git/commit-message", "commit-message", "Тело скила.")
    runner = CliRunner()
    t = _run(runner, ["skills", "tree", "--root", str(tmp_path), "--output", "table"])
    assert "coding/ (1)" in t.output  # own 0 + git/ 1 — раньше печаталось (0)
    assert "git/ (1)" in t.output
