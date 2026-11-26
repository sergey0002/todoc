# tests/cli/test_bugfixes.py — регресс-тесты исправлений BUG-001..010 (исполнение репортов)
import json
from pathlib import PurePosixPath

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


# --- BUG-004: docs edit — вставка и удаление строк -----------------------------------

def test_docs_edit_insert_and_delete_ops(tmp_path):
    _init(tmp_path)
    (tmp_path / "inbox").mkdir()
    (tmp_path / "inbox/doc.md").write_text("# Титул\n\nстрока2\nстрока3\n", encoding="utf-8")
    patch = {"ops": [
        {"op": "insert_after", "line": 2, "text": "новая строка"},
        {"op": "delete", "line": 4},
        {"op": "insert_after", "line": 0, "text": ["шапка1", "шапка2"]},
    ]}
    pf = tmp_path / "patch.json"
    pf.write_text(json.dumps(patch, ensure_ascii=False), encoding="utf-8")
    runner = CliRunner()
    r = _run(runner, ["docs", "edit", "--root", str(tmp_path), "--id", "doc:inbox/doc.md",
                      "--patch-file", str(pf)])
    assert _json(r)["data"]["preview"] is True  # preview не пишет
    assert (tmp_path / "inbox/doc.md").read_text(encoding="utf-8").startswith("# Титул")
    r = _run(runner, ["docs", "edit", "--root", str(tmp_path), "--id", "doc:inbox/doc.md",
                      "--patch-file", str(pf), "--apply"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "inbox/doc.md").read_text(encoding="utf-8") == (
        "шапка1\nшапка2\n# Титул\n\nновая строка\nстрока3\n")


# --- BUG-007: docs links — инвентаризация локальных ссылок ---------------------------

def test_docs_links_counts_and_broken(tmp_path):
    _init(tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.md").write_text(
        "---\ntitle: A\n---\n\n# A\n\nСм. [[b]] и [[битая-цель]] и [внешняя](https://x.example) "
        "и [локальная](c.md)\n", encoding="utf-8")
    (inbox / "b.md").write_text("---\ntitle: B\n---\n\n# B\n", encoding="utf-8")
    (inbox / "c.md").write_text("---\ntitle: C\n---\n\n# C\n", encoding="utf-8")
    runner = CliRunner()
    r = _run(runner, ["docs", "links", "--root", str(tmp_path)])
    d = _json(r)["data"]
    assert d["total"] == 3  # [[b]], [[битая-цель]], [локальная](c.md); https — не локальная
    assert d["broken"] == 1
    assert d["items"][0]["path"] == "inbox/a.md"
    assert d["items"][0]["target"] == "битая-цель"
    assert d["items"][0]["kind"] == "wikilink"
    assert d["items"][0]["line"] >= 1


# --- BUG-001/BUG-002: явный doc_type без правила + файлы change open -----------------

def test_explain_path_explicit_doc_type_without_rule(tmp_path):
    _init(tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "custom.md").write_text(
        "---\ntitle: \"Кастом\"\ndoc_type: plan\n---\n\n# Кастом\n", encoding="utf-8")
    runner = CliRunner()
    r = _run(runner, ["explain-path", "--root", str(tmp_path), "inbox/custom.md"])
    d = _json(r)["data"]
    assert d["doc_type"] == "plan"          # раньше: unknown
    assert d["rule_source"] == "front-matter"  # явное объявление — высший приоритет


def test_change_open_files_resolve_note(tmp_path):
    _init(tmp_path)
    runner = CliRunner()
    r = _run(runner, ["change", "open", "--root", str(tmp_path), "--title", "Проверка"])
    assert r.exit_code == 0, r.output
    change_dir = PurePosixPath(_json(r)["data"]["path"]).parent.as_posix()
    for name in ("proposal.md", "tasks.md"):
        target = f"{change_dir}/{name}"
        assert (tmp_path / target).is_file(), target
        e = _run(runner, ["explain-path", "--root", str(tmp_path), target])
        d = _json(e)["data"]
        assert d["doc_type"] == "note", (name, d["doc_type"], d["rule_source"])
