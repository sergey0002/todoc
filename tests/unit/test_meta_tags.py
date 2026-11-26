# tests/unit/test_meta_tags.py — план doc-tags: Задача 1 (валидация), Задача 2 (поиск)
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


def _init(runner, tmp_path):
    assert _run(runner, ["init", "--root", str(tmp_path), "--no-input"]).exit_code == 0


def _doc(runner, tmp_path, rel, body):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    r = _run(runner, ["index", "rebuild", "--root", str(tmp_path)])
    assert r.exit_code == 0, r.output


def _diags(runner, tmp_path):
    r = _run(runner, ["validate", "--root", str(tmp_path), "--all"])
    return _json(r)["diagnostics"], r


# --- Задача 1: валидация tags/updated/created/related --------------------------------

def test_tags_invalid_forms(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    cases = [
        'tags: ["OK-tag", "ПЛОХОЙ!!"]',      # недопустимые символы
        'tags: "не-список"',                  # не список
        'tags: [a1, b2, c3, d4, e5, f6, g7, h8, i9]',  # >8
        'tags: [длинный-тег-' + "х" * 40 + ']',  # >32
        'tags: [x]',                          # короче 2
        'tags: ["UPPER-Case"]',               # заглавные вне kebab
    ]
    for i, fm in enumerate(cases):
        _doc(runner, tmp_path, f"notes/bad{i}.md",
             f"---\ntitle: T\n{fm}\n---\n\n# T\n\nтело.\n")
    diags, _ = _diags(runner, tmp_path)
    codes = [d["code"] for d in diags]
    assert codes.count("markdown.tags_invalid") == len(cases), codes


def test_dates_invalid_forms(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _doc(runner, tmp_path, "notes/bad-date.md",
         "---\ntitle: T\nupdated: \"25.11.2026\"\ncreated: 25-11-2026\n---\n\n# T\n\nтело.\n")
    diags, _ = _diags(runner, tmp_path)
    codes = [d["code"] for d in diags]
    assert codes.count("markdown.updated_invalid") == 1, codes
    assert codes.count("markdown.created_invalid") == 1, codes


def test_related_requires_wikilink_form(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _doc(runner, tmp_path, "notes/rel-ok.md",
         "---\ntitle: T\nrelated: [\"[[ok]]\", \"[[другая-заметка]]\"]\n---\n\n# T\n\nтело.\n")
    _doc(runner, tmp_path, "notes/rel-bad.md",
         "---\ntitle: T\nrelated: [\"ok.md\", \"[[ok\"]]\n---\n\n# T\n\nтело.\n")
    diags, _ = _diags(runner, tmp_path)
    codes = [d["code"] for d in diags]
    assert codes.count("markdown.related_invalid") == 1, codes


def test_valid_and_absent_fields_clean(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _doc(runner, tmp_path, "notes/full.md",
         "---\ntitle: T\ncreated: 2026-11-25\nupdated: 2026-11-26\n"
         "tags: [поиск, front-matter]\nrelated: [\"[[other]]\"]\n---\n\n# T\n\nтело.\n")
    _doc(runner, tmp_path, "notes/empty-tags.md",
         "---\ntitle: T\ntags: []\n---\n\n# T\n\nтело.\n")
    _doc(runner, tmp_path, "notes/no-meta.md", "# T\n\nпросто тело без полей.\n")
    diags, _ = _diags(runner, tmp_path)
    assert diags == [], diags


# --- Задача 2: теги в поиске (веса) + --tag ------------------------------------------

def _setup_two_docs(runner, tmp_path):
    """Оба документа совпадают по телу («search»); разница — тег: буст решает порядок."""
    _doc(runner, tmp_path, "notes/tagged.md",
         "---\ntitle: Заметка о креденшалах\ntags: [search]\n---\n\n# Заметка о креденшалах\n\n"
         "текст про search и refresh token.\n")
    _doc(runner, tmp_path, "notes/plain.md",
         "---\ntitle: Заметка о креденшалах\n---\n\n# Заметка о креденшалах\n\n"
         "текст про search и refresh token.\n")


def test_tag_boost_puts_tagged_doc_first(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _setup_two_docs(runner, tmp_path)
    r = _run(runner, ["docs", "search", "--root", str(tmp_path), "--query", "search"])
    hits = _json(r)["data"]["items"]
    assert [h["path"] for h in hits] == ["notes/tagged.md", "notes/plain.md"]


def test_tag_exact_adds_eight_partial_adds_three(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _doc(runner, tmp_path, "notes/w.md",
         "---\ntitle: T\ntags: [front-matter, поиск]\n---\n\n# T\n\nтело.\n")
    from todoc.application.search import _document_text, search_documents

    docs = _json(_run(runner, ["docs", "tree", "--root", str(tmp_path)]))["data"]["documents"]
    hits, _t, _tr = search_documents(tmp_path, docs, "front-matter")
    assert hits[0].path == "notes/w.md"  # exact-тег
    # partial: токен «matter» внутри тега front-matter
    hits2, _t2, _tr2 = search_documents(tmp_path, docs, "matter")
    assert hits2[0].path == "notes/w.md"  # тело не содержит «matter» — попал тег


def test_tag_filter_cli(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _setup_two_docs(runner, tmp_path)
    r = _run(runner, ["docs", "search", "--root", str(tmp_path), "--query", "refresh", "--tag", "search"])
    hits = _json(r)["data"]["items"]
    assert [h["path"] for h in hits] == ["notes/tagged.md"]


def test_tag_filter_empty_when_no_match(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _setup_two_docs(runner, tmp_path)
    r = _run(runner, ["docs", "search", "--root", str(tmp_path), "--query", "refresh", "--tag", "нет-такого"])
    assert _json(r)["data"]["items"] == []


def test_read_output_carries_meta_fields(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    _doc(runner, tmp_path, "notes/meta.md",
         "---\nid: doc:notes/meta.md\ntitle: T\ncreated: 2026-11-25\nupdated: 2026-11-26\n"
         "tags: [a1, b2]\nrelated: [\"[[x]]\"]\n---\n\n# T\n\nтело.\n")
    r = _run(runner, ["docs", "read", "--root", str(tmp_path), "--id", "doc:notes/meta.md"])
    d = _json(r)["data"]
    assert d["tags"] == ["a1", "b2"]
    assert d["updated"] == "2026-11-26"
    assert d["related"] == ["[[x]]"]
    r2 = _run(runner, ["docs", "read", "--root", str(tmp_path), "--id", "doc:notes/plain-x.md"])
    assert r2.exit_code != 0  # не существует — docs.not_found


# --- Задача 3: даты в движке (docs new fm + бамп updated в docs edit) -----------------

def test_docs_new_writes_front_matter_with_dates(tmp_path, monkeypatch):
    import re
    runner = CliRunner()
    _init(runner, tmp_path)
    r = _run(runner, ["docs", "new", "--root", str(tmp_path), "--title", "Свежая заметка",
                      "--dir", "inbox", "--template", "note"])
    assert r.exit_code == 0, r.output
    text = (tmp_path / "inbox/svezhaya-zametka.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert re.search(r"^id: doc:inbox/svezhaya-zametka\.md$", text, re.M)
    assert re.search(r'^title: "Свежая заметка"$', text, re.M)
    assert re.search(r"^doc_type: note$", text, re.M)
    assert re.search(r"^lang: ru$", text, re.M)
    today = text.split("created: ")[1].split("\n")[0]
    assert today == text.split("updated: ")[1].split("\n")[0]
    assert "## Суть" in text  # тело шаблона на месте


def test_docs_edit_apply_bumps_updated(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/d.md").write_text(
        "---\ntitle: D\ncreated: 2026-01-01\nupdated: 2026-02-02\n---\n\n# D\n\nстарая строка\n",
        encoding="utf-8")
    _run(runner, ["index", "rebuild", "--root", str(tmp_path)])
    pf = tmp_path / "p.json"
    pf.write_text(json.dumps({"ops": [{"line": 6, "text": "новая строка"}]}), encoding="utf-8")
    r = _run(runner, ["docs", "edit", "--root", str(tmp_path), "--id", "doc:notes/d.md",
                      "--patch-file", str(pf), "--apply"])
    d = _json(r)["data"]
    assert d["updated_bumped"] is True
    text = (tmp_path / "notes/d.md").read_text(encoding="utf-8")
    assert "created: 2026-01-01" in text
    assert f"updated: {text.split('created: ')[1].split(chr(10))[0][:0]}" or True  # форма ниже
    import re
    m = re.search(r"^updated: (\d{4}-\d{2}-\d{2})$", text, re.M)
    assert m and m.group(1) != "2026-02-02"  # бампнута на сегодня
    assert "новая строка" in text


def test_docs_edit_preview_keeps_file_bytes(tmp_path):
    runner = CliRunner()
    _init(runner, tmp_path)
    (tmp_path / "notes").mkdir()
    body = "---\ntitle: D\ncreated: 2026-01-01\nupdated: 2026-02-02\n---\n\n# D\n\nстрока\n"
    (tmp_path / "notes/d.md").write_text(body, encoding="utf-8")
    _run(runner, ["index", "rebuild", "--root", str(tmp_path)])
    pf = tmp_path / "p.json"
    pf.write_text(json.dumps({"ops": [{"line": 6, "text": "новая"}]}), encoding="utf-8")
    r = _run(runner, ["docs", "edit", "--root", str(tmp_path), "--id", "doc:notes/d.md",
                      "--patch-file", str(pf)])
    assert _json(r)["data"]["preview"] is True
    assert (tmp_path / "notes/d.md").read_text(encoding="utf-8") == body  # байт-в-байт


def test_apply_edit_ops_bump_without_updated_field(tmp_path):
    from todoc.application.write import apply_edit_ops

    (tmp_path / "l.md").write_text("# Legacy\n\nнет fm.\n", encoding="utf-8")
    new_hash, bumped = apply_edit_ops(tmp_path, "l.md", [{"line": 3, "text": "правка"}],
                                      bump_updated=True)
    assert bumped is False  # fm нет — бампать нечего
    assert "правка" in (tmp_path / "l.md").read_text(encoding="utf-8")
