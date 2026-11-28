"""Фаза 1: журнал событий, снимки «до», откат, метки (K35, K36, K37)."""

import hashlib
import json

import pytest

from todoc.adapters.history import journal, objects
from todoc.adapters.history.backends import EmbeddedBackend, GitBackend, detect_backend, resolve_backend
from todoc.adapters.history.store import FileHistoryStore
from todoc.application import history as H


@pytest.fixture()
def doc(root):
    notes = root / "notes"
    notes.mkdir()
    path = notes / "a.md"
    path.write_text('---\ntitle: "Заметка"\ndoc_type: note\n---\n\n# Заметка\n\n'
                    + "".join(f"строка {i}\n" for i in range(1, 21)), encoding="utf-8")
    return path


def _edit(path, line, text):
    """Правка через тот же путь, что и CLI: с записью события в журнал."""
    root = path.parent.parent  # path == <root>/notes/a.md
    before = path.read_bytes()
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[line - 1] = text
    after = ("\n".join(lines) + "\n").encode("utf-8")
    path.write_bytes(after)
    return H.record_write(root, "notes/a.md", before, after, kind="doc.edit", basis="test")


# --- журнал ------------------------------------------------------------------


def test_append_event_returns_stable_rev(root):
    rev1 = journal.append_event(root, {"kind": "doc.edit", "paths": []})
    rev2 = journal.append_event(root, {"kind": "doc.edit", "paths": []})
    # одинаковое содержимое -> одинаковый rev: счётчик не нужен
    assert rev1 == rev2 and len(rev1) == 12


def test_different_events_get_different_revs(root):
    assert journal.append_event(root, {"kind": "a"}) != journal.append_event(root, {"kind": "b"})


def test_iter_events_skips_broken_line(root):
    journal.append_event(root, {"kind": "doc.edit"})
    with journal.journal_path(root).open("a", encoding="utf-8") as fh:
        fh.write("{ оборвано\n")
    journal.append_event(root, {"kind": "doc.fix"})
    kinds = [e["kind"] for e in journal.iter_events(root)]
    assert kinds == ["doc.edit", "doc.fix"]
    assert journal.truncated_last_line(root) is False  # битая строка не последняя


def test_truncated_last_line_detected(root):
    journal.append_event(root, {"kind": "doc.edit"})
    with journal.journal_path(root).open("a", encoding="utf-8") as fh:
        fh.write('{"kind": "doc.ed')
    assert journal.truncated_last_line(root) is True


def test_journal_diagnostics_reports_truncation(root):
    journal.journal_path(root).parent.mkdir(parents=True, exist_ok=True)
    with journal.journal_path(root).open("w", encoding="utf-8") as fh:
        fh.write('{"kind": "doc.ed')
    diags = H.journal_diagnostics("ds", root)
    assert [d.code for d in diags] == [H.JOURNAL_TRUNCATED]
    assert diags[0].severity == "warning"


# --- снимки ------------------------------------------------------------------


def test_snapshot_roundtrip_and_dedup(root):
    data = "содержимое файла".encode("utf-8") * 50
    first = objects.write_snapshot(root, data)
    second = objects.write_snapshot(root, data)
    assert first == second
    assert objects.read_snapshot(root, first) == data
    assert objects.count_objects(root) == 1


def test_snapshot_of_unreadable_object(root):
    assert objects.read_snapshot(root, "sha256:" + "0" * 64) is None


# --- диапазоны изменений -----------------------------------------------------


def test_changed_ranges_single_line():
    assert H.changed_ranges("a\nb\nc\n", "a\nX\nc\n") == [[2, 2]]


def test_changed_ranges_insertion_and_deletion():
    assert H.changed_ranges("a\nb\nc\n", "a\nc\n") == [[2, 2]]
    assert H.changed_ranges("a\nc\n", "a\nb\nc\n") == [[2, 2]]


def test_changed_ranges_empty_when_equal():
    assert H.changed_ranges("a\nb\n", "a\nb\n") == []


# --- запись события ----------------------------------------------------------


def test_record_write_stores_before_and_ranges(root, doc):
    rev = _edit(doc, 9, "изменено")
    events = journal.read_events(root)
    assert len(events) == 1 and events[0]["rev"] == rev
    item = events[0]["paths"][0]
    assert item["ranges"] == [[9, 9]]
    assert item["before"].startswith("sha256:")
    assert item["after"].startswith("sha256:")


def test_record_write_on_create_has_no_before(root):
    target = root / "new.md"
    target.write_text("новое\n", encoding="utf-8")
    H.record_write(root, "new.md", None, "новое\n".encode("utf-8"), kind="doc.create")
    item = journal.read_events(root)[0]["paths"][0]
    assert item["before"] is None and item["ranges"] == []


def test_record_write_carries_change_id(root, doc):
    before = doc.read_bytes()
    H.record_write(root, "notes/a.md", before, before, kind="doc.edit", change_id="change:x")
    assert journal.read_events(root)[0]["change_id"] == "change:x"


# --- чтение на ревизии -------------------------------------------------------


def test_content_at_returns_state_after_revision(root, doc):
    """show <rev> — состояние ПОСЛЕ события (как git show <c>:<path>)."""
    first = _edit(doc, 9, "первая правка")
    _edit(doc, 10, "вторая правка")
    text, status = H.show(root, first, "notes/a.md")
    assert status == "ok"
    assert "первая правка" in text and "вторая правка" not in text


def test_before_content_undoes_one_event(root, doc):
    """revert <rev> — состояние ДО события (как git revert <c>)."""
    rev = _edit(doc, 9, "изменено")
    data, status = H.before_content(root, rev, "notes/a.md")
    assert status == "ok"
    assert "изменено".encode("utf-8") not in data
    assert "строка 2".encode("utf-8") in data


def test_before_content_of_create_is_absent(root):
    H.record_write(root, "new.md", None, b"x\n", kind="doc.create")
    rev = journal.read_events(root)[0]["rev"]
    data, status = H.before_content(root, rev, "new.md")
    assert data is None and status == "no_before"


def test_before_content_unknown_revision(root):
    data, status = H.before_content(root, "неттакойрев", "a.md")
    assert data is None and status == "revision_unknown"


def test_missing_object_reported(root, doc):
    rev = _edit(doc, 9, "изменено")
    digest = journal.read_events(root)[0]["paths"][0]["before"]
    objects.remove_object(root, digest)
    data, status = H.before_content(root, rev, "notes/a.md")
    assert data is None and status == "object_missing"


# --- откат -------------------------------------------------------------------


def test_revert_plan_and_byte_exact_restore(root, doc):
    """K35: откат восстанавливает содержимое байт-в-байт."""
    snapshots = []
    for i in range(20):
        snapshots.append(doc.read_bytes())
        _edit(doc, 8 + (i % 20), f"правка {i}")
    events = journal.read_events(root)
    assert len(events) == 20
    for index, event in enumerate(events):
        plan = H.revert_plan(root, event["rev"], "notes/a.md")
        assert plan["status"] == "ok"
        doc.write_text(plan["content"], encoding="utf-8")
        assert doc.read_bytes() == snapshots[index], f"расхождение на шаге {index}"


def test_revert_plan_reports_missing(root):
    plan = H.revert_plan(root, "неттакойрев", "a.md")
    assert plan["status"] == "revision_unknown"


# --- лента по разделу (K37) --------------------------------------------------


@pytest.fixture()
def sectioned(root):
    path = root / "s.md"
    path.write_text("---\ntitle: \"Р\"\n---\n\n# Р\n\n## Решение\n\nтекст решения\n\n"
                    "## Итоги\n\nтекст итогов\n", encoding="utf-8")
    return path


def test_section_feed_isolates_events(root, sectioned):
    """K37: лента раздела отдаёт только события, пересекающие его границы."""
    lines = sectioned.read_text(encoding="utf-8").splitlines()
    before = sectioned.read_bytes()
    lines[8] = "изменённое решение"
    after = ("\n".join(lines) + "\n").encode("utf-8")
    sectioned.write_bytes(after)
    H.record_write(root, "s.md", before, after, kind="doc.edit")

    lines = after.decode("utf-8").splitlines()
    lines[12] = "изменённые итоги"
    after2 = ("\n".join(lines) + "\n").encode("utf-8")
    sectioned.write_bytes(after2)
    H.record_write(root, "s.md", after, after2, kind="doc.edit")

    solution, _total, _t = H.log(root, path="s.md", section="## Решение")
    assert len(solution) == 1 and solution[0]["paths"][0]["ranges"] == [[9, 9]]
    results, _t2, _t3 = H.log(root, path="s.md", section="## Итоги")
    assert len(results) == 1 and results[0]["paths"][0]["ranges"] == [[13, 13]]


def test_log_section_requires_path(root, sectioned):
    events, total, truncated = H.log(root, section="## Решение")
    # без --path фильтр по разделу не применяется: раздел ищется внутри файла
    assert total == 0


# --- фильтрация журнала ------------------------------------------------------


def test_log_filters_and_pagination(root, doc):
    for i in range(5):
        _edit(doc, 9, f"правка {i}")
    window, total, truncated = H.log(root, path="notes/a.md", limit=2)
    assert total == 5 and len(window) == 2 and truncated is True
    second, _t, _tr = H.log(root, path="notes/a.md", limit=2, cursor=2)
    assert [e["rev"] for e in second] != [e["rev"] for e in window]


def test_log_newest_first(root, doc):
    _edit(doc, 9, "первая")
    _edit(doc, 10, "вторая")
    events, _t, _tr = H.log(root)
    # событие хранит хеши и диапазоны, а не текст: порядок проверяем по диапазону
    assert events[0]["paths"][0]["ranges"] == [[10, 10]]
    assert events[1]["paths"][0]["ranges"] == [[9, 9]]


def test_log_filter_by_kind(root, doc):
    before = doc.read_bytes()
    H.record_write(root, "notes/a.md", before, before, kind="doc.fix")
    _edit(doc, 9, "правка")
    events, total, _t = H.log(root, kind="doc.fix")
    assert total == 1 and events[0]["kind"] == "doc.fix"


# --- метки -------------------------------------------------------------------


def test_tag_and_resolve(root, doc):
    rev = _edit(doc, 9, "правка")
    H.add_tag(root, "v1", rev, "релиз")
    assert H.resolve_rev(root, "v1") == rev
    assert H.resolve_rev(root, rev) == rev
    assert H.read_refs(root)["tags"]["v1"]["message"] == "релиз"


def test_refs_tolerate_corruption(root):
    H.refs_path(root).parent.mkdir(parents=True, exist_ok=True)
    H.refs_path(root).write_text("не json", encoding="utf-8")
    assert H.read_refs(root) == {"head": None, "tags": {}}


def test_set_head(root, doc):
    rev = _edit(doc, 9, "правка")
    H.set_head(root, rev)
    assert H.read_refs(root)["head"] == rev


# --- сборка мусора и миграция ------------------------------------------------


def test_gc_removes_orphans_only(root, doc):
    _edit(doc, 9, "одна")
    _edit(doc, 10, "две")
    referenced = objects.count_objects(root)
    # объект, на который никто не ссылается
    objects.write_snapshot(root, "сирота".encode("utf-8"))
    assert objects.count_objects(root) == referenced + 1
    result = H.gc(root)
    assert result["orphans_removed"] == 1
    assert objects.count_objects(root) == referenced


def test_gc_purge_before(root, doc):
    _edit(doc, 9, "правка")
    result = H.gc(root, purge_before="2099-01-01T00:00:00Z")
    assert result["removed_events"] == 1 and result["kept_events"] == 0
    assert journal.read_events(root) == []


def test_gc_dry_run_writes_nothing(root, doc):
    _edit(doc, 9, "правка")
    before = objects.count_objects(root)
    H.gc(root, purge_before="2099-01-01T00:00:00Z", dry_run=True)
    assert objects.count_objects(root) == before
    assert len(journal.read_events(root)) == 1


def test_adopt_creates_baseline(root, doc):
    result = H.adopt(root, [{"path": "notes/a.md", "hash": "sha256:x"}])
    assert result["paths"] == 1
    events = journal.read_events(root)
    assert events[0]["kind"] == "snapshot"
    assert H.read_refs(root)["head"] == result["rev"]


def test_export_copies_history(root, doc, tmp_path):
    _edit(doc, 9, "правка")
    target = tmp_path / "backup"
    result = H.export(root, target)
    assert result["exported"] >= 2
    assert (target / "journal.jsonl").is_file()


# --- бэкенды -----------------------------------------------------------------


def test_embedded_backend_always_snapshots(root):
    backend = EmbeddedBackend(root)
    assert backend.available() is True
    assert backend.head() is None
    assert backend.needs_snapshot("a.md", None) is True
    assert backend.needs_snapshot("a.md", "sha256:x") is True


def test_embedded_read_at(root):
    backend = EmbeddedBackend(root)
    digest = objects.write_snapshot(root, "данные".encode("utf-8"))
    assert backend.read_at(digest, "a.md") == "данные".encode("utf-8")
    assert backend.read_at(None, "a.md") is None


def test_detect_backend_outside_repo_is_embedded(tmp_path):
    assert detect_backend(tmp_path) == "embedded"


def test_resolve_backend_degrades_when_git_missing(tmp_path):
    backend, reason = resolve_backend(tmp_path, "git")
    assert backend.name == "embedded"
    assert reason == "git"


def test_resolve_backend_honours_config(tmp_path):
    backend, reason = resolve_backend(tmp_path, "embedded")
    assert backend.name == "embedded" and reason is None


def test_configured_backend_reads_dataset():
    assert H.configured_backend({"history": {"backend": "git"}}) == "git"
    assert H.configured_backend({}) is None
    assert H.configured_backend({"history": "не словарь"}) is None


def test_git_backend_needs_snapshot_without_prior_head(tmp_path):
    backend = GitBackend(tmp_path)
    assert backend.needs_snapshot("a.md", None) is True


# --- объекты: ветки ошибок ---------------------------------------------------


def test_objects_bytes_and_missing_dir(root):
    assert objects.objects_bytes(root) == 0
    assert objects.count_objects(root) == 0
    objects.write_snapshot(root, "данные".encode("utf-8"))
    assert objects.objects_bytes(root) > 0


def test_remove_object_missing(root):
    assert objects.remove_object(root, "sha256:" + "0" * 64) is False


def test_corrupt_object_returns_none(root):
    digest = objects.write_snapshot(root, "данные".encode("utf-8"))
    objects.object_path(root, digest).write_bytes("не zlib".encode("utf-8"))
    assert objects.read_snapshot(root, digest) is None


# --- журнал: ветки ошибок ----------------------------------------------------


def test_iter_events_skips_non_dict_lines(root):
    journal.journal_path(root).parent.mkdir(parents=True, exist_ok=True)
    journal.journal_path(root).write_text("[1, 2]\n\n{\"kind\": \"doc.edit\"}\n", encoding="utf-8")
    assert [e["kind"] for e in journal.iter_events(root)] == ["doc.edit"]


def test_truncated_last_line_on_empty_and_missing(root):
    assert journal.truncated_last_line(root) is False
    journal.journal_path(root).parent.mkdir(parents=True, exist_ok=True)
    journal.journal_path(root).write_text("\n\n", encoding="utf-8")
    assert journal.truncated_last_line(root) is False


def test_rewrite_replaces_journal(root):
    journal.append_event(root, {"kind": "a"})
    journal.append_event(root, {"kind": "b"})
    journal.rewrite(root, [{"kind": "b"}])
    assert [e["kind"] for e in journal.iter_events(root)] == ["b"]


# --- git-бэкенд на настоящем репозитории -------------------------------------


@pytest.fixture()
def git_repo(tmp_path):
    import shutil as _sh
    import subprocess as _sp

    if _sh.which("git") is None:
        pytest.skip("git недоступен")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.md").write_text("первая\n", encoding="utf-8")

    def git(*args):
        return _sp.run(("git", *args), cwd=str(repo), capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    git("add", "-A")
    git("commit", "-qm", "первый")
    return repo


def test_git_backend_available_and_head(git_repo):
    backend = GitBackend(git_repo)
    assert backend.available() is True
    head = backend.head()
    assert head and len(head) == 40


def test_git_backend_read_at(git_repo):
    backend = GitBackend(git_repo)
    head = backend.head()
    assert backend.read_at(head, "a.md") == "первая\n".encode("utf-8")
    assert backend.read_at(None, "a.md") is None
    assert backend.read_at(head, "нет.md") is None


def test_git_backend_needs_snapshot_by_gap_filling(git_repo):
    """K-правило §18: снимок нужен, когда прошлое состояние недостижимо из git."""
    backend = GitBackend(git_repo)
    head = backend.head()
    assert backend.needs_snapshot("a.md", head) is True      # тот же HEAD — пробел
    assert backend.needs_snapshot("a.md", "0" * 40) is False  # другой HEAD — git достанет
    assert backend.needs_snapshot("a.md", None) is True


def test_detect_backend_inside_repo(git_repo):
    assert detect_backend(git_repo) == "git"


def test_resolve_backend_git_when_available(git_repo):
    backend, reason = resolve_backend(git_repo, "git")
    assert backend.name == "git" and reason is None


def test_resolve_backend_default_outside_repo(tmp_path):
    backend, reason = resolve_backend(tmp_path, None)
    assert backend.name == "embedded" and reason is None


# --- ветки деградации --------------------------------------------------------


def test_refs_tolerate_non_dict(root):
    H.refs_path(root).parent.mkdir(parents=True, exist_ok=True)
    H.refs_path(root).write_text("[1, 2]", encoding="utf-8")
    assert H.read_refs(root) == {"head": None, "tags": {}}


def test_record_write_on_binary_content_keeps_event(root):
    """Бинарное содержимое: диапазоны считаются по заменённым символам, событие цело."""
    before = b"\x00\x01\x02\x03"
    after = b"\x00\x01\xff\x03"
    rev = H.record_write(root, "bin.dat", before, after, kind="doc.edit")
    item = journal.read_events(root)[0]["paths"][0]
    assert rev and item["ranges"] == [[1, 1]] and item["before"]


def test_record_write_extra_fields(root, doc):
    H.record_write(root, "notes/a.md", doc.read_bytes(), doc.read_bytes(),
                   kind="doc.edit", extra={"note": "внешняя правка"})
    assert journal.read_events(root)[0]["paths"][0]["note"] == "внешняя правка"


def test_content_at_unknown_revision(root, doc):
    data, status = H.content_at(root, "неттакойрев", "notes/a.md")
    assert data is None and status == "revision_unknown"


def test_content_at_missing_file(root):
    data, status = H.content_at(root, None, "нет.md")
    assert data is None and status == "missing"


def test_content_at_unreadable_file(root):
    (root / "locked.md").write_text("секрет", encoding="utf-8")
    (root / "locked.md").chmod(0)
    try:
        data, status = H.content_at(root, None, "locked.md")
        assert data is None and status == "unreadable"
    finally:
        (root / "locked.md").chmod(0o644)


def test_content_at_falls_back_to_git(root, git_repo):
    """Когда снимка нет, содержимое достаётся из git по сохранённому HEAD."""
    backend = GitBackend(git_repo)
    first = H.record_write(git_repo, "a.md", None, "x\n".encode("utf-8"),
                           kind="doc.create", backend=backend)
    H.record_write(git_repo, "a.md", None, "y\n".encode("utf-8"),
                   kind="doc.create", backend=backend)
    data, status = H.content_at(git_repo, first, "a.md", backend)
    assert status == "ok" and data == "первая\n".encode("utf-8")


def test_before_content_falls_back_to_git(root, git_repo):
    backend = GitBackend(git_repo)
    rev = H.record_write(git_repo, "a.md", None, "x\n".encode("utf-8"),
                         kind="doc.create", backend=backend)
    data, status = H.before_content(git_repo, rev, "a.md", backend)
    assert status == "ok" and data == "первая\n".encode("utf-8")


def test_invalid_utf8_reported_as_unreadable(root, doc):
    """Бинарный образ: show и revert_plan сообщают status=unreadable, а не падают."""
    first = _edit(doc, 9, "первая правка")
    broken = b"\xff\xfe\x00" + "бинарь".encode("utf-8")
    doc.write_bytes(broken)
    H.record_write(root, "notes/a.md", broken, broken, kind="doc.edit")
    text, status = H.show(root, first, "notes/a.md")
    assert text is None and status == "unreadable"
    plan = H.revert_plan(root, journal.read_events(root)[-1]["rev"], "notes/a.md")
    assert plan["status"] == "unreadable"


def test_revert_plan_without_revision(root):
    assert H.revert_plan(root, None, "a.md")["status"] == "revision_unknown"
    assert H.revert_plan(root, "", "a.md")["status"] == "revision_unknown"


def test_resolve_rev_passes_through_and_rejects_empty(root):
    """Неизвестное имя возвращается как есть (это может быть rev), пустое — None."""
    assert H.resolve_rev(root, "abc123") == "abc123"
    assert H.resolve_rev(root, "") is None


# --- фильтры журнала ---------------------------------------------------------


def test_log_filters_by_change_id(root, doc):
    before = doc.read_bytes()
    H.record_write(root, "notes/a.md", before, before, kind="doc.edit", change_id="change:x")
    _edit(doc, 9, "без change_id")
    events, total, _t = H.log(root, change_id="change:x")
    assert total == 1 and events[0]["change_id"] == "change:x"
    assert H.log(root, change_id="change:нет")[1] == 0


def test_log_filters_by_time_window(root, doc):
    _edit(doc, 9, "правка")
    assert H.log(root, since="2099-01-01T00:00:00Z")[1] == 0
    assert H.log(root, until="2000-01-01T00:00:00Z")[1] == 0
    assert H.log(root, since="2000-01-01T00:00:00Z", until="2099-01-01T00:00:00Z")[1] == 1


def test_log_unknown_tag_selects_nothing(root, doc):
    _edit(doc, 9, "правка")
    assert H.log(root, tag="нет")[1] == 0


def test_log_section_unknown_selector(root, doc):
    _edit(doc, 9, "правка")
    assert H.log(root, path="notes/a.md", section="## Нет")[1] == 0


def test_section_bounds_on_missing_file(root):
    assert H._section_bounds(root, "нет.md", "## Решение") is None


def test_section_bounds_on_unreadable_file(root):
    target = root / "locked.md"
    target.write_text("## Решение\n", encoding="utf-8")
    target.chmod(0)
    try:
        assert H._section_bounds(root, "locked.md", "## Решение") is None
    finally:
        target.chmod(0o644)


def test_blame_unknown_section_returns_empty(root, doc):
    _edit(doc, 9, "правка")
    assert H.blame(root, "notes/a.md", section="## Нет") == []


# --- сборка мусора и экспорт: крайние случаи ---------------------------------


def test_gc_keep_objects_without_history_dir(root):
    result = H.gc(root, keep_objects=0)
    assert result["objects_before"] == 0 and result["orphans_removed"] == 0


def test_gc_trim_honours_keep_objects_even_for_referenced(root, doc):
    """``keep_objects`` — настоящий потолок: иначе он не значил бы ничего.

    Снимки, на которые ссылается журнал, больше не защищены: все «живые» снимки
    защищены ссылкой, а незащищённых к этому моменту уже нет, поэтому защита
    превращала опцию в заглушку. Цена явная и уже поддержана чтением — у затёртой
    ревизии ``before_content`` вернёт ``object_missing``, а не выдуманное содержимое.
    """
    rev = _edit(doc, 9, "одна")
    _edit(doc, 10, "две")
    referenced = len({i["before"] for e in journal.read_events(root)
                      for i in e["paths"] if i.get("before")})
    assert referenced >= 2
    result = H.gc(root, keep_objects=0)
    assert result["objects_trimmed"] == referenced
    assert objects.count_objects(root) == 0
    data, status = H.before_content(root, rev, "notes/a.md")
    assert data is None and status == "object_missing"


def test_adopt_skips_missing_paths(root, doc):
    result = H.adopt(root, [{"path": "notes/a.md"}, {"path": "нет.md"}])
    assert result["paths"] == 1


def test_export_without_history_dir(root, tmp_path):
    result = H.export(root, tmp_path / "backup")
    assert result["exported"] == 0 and not (tmp_path / "backup").exists()


def test_journal_diagnostics_clean(root):
    assert H.journal_diagnostics("ds", root) == []


# --- оставшиеся ветки: git недоступен, отказы ФС -----------------------------


def test_git_helpers_return_none_without_git(root, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _name: None)
    backend = GitBackend(root)
    assert backend.available() is False
    assert backend.head() is None
    assert backend.read_at("0" * 40, "a.md") is None


def test_git_helpers_survive_subprocess_failure(root, monkeypatch):
    def boom(*_args, **_kwargs):
        raise OSError("git сломался")

    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/git")
    monkeypatch.setattr("subprocess.run", boom)
    backend = GitBackend(root)
    assert backend.available() is False
    assert backend.head() is None
    assert backend.read_at("0" * 40, "a.md") is None


def test_truncated_last_line_survives_unreadable_journal(root):
    journal.append_event(root, {"kind": "doc.edit"})
    journal.journal_path(root).chmod(0)
    try:
        assert journal.truncated_last_line(root) is False
    finally:
        journal.journal_path(root).chmod(0o644)


def test_remove_object_survives_locked_directory(root):
    digest = objects.write_snapshot(root, "данные".encode("utf-8"))
    parent = objects.object_path(root, digest).parent
    parent.chmod(0o555)
    try:
        assert objects.remove_object(root, digest) is False
        assert objects.count_objects(root) == 1
    finally:
        parent.chmod(0o755)


def test_trim_objects_survives_locked_directory(root, doc):
    _edit(doc, 9, "одна")
    _edit(doc, 10, "две")
    locked = next(objects.objects_dir(root).iterdir())
    locked.chmod(0o555)
    try:
        H.gc(root, keep_objects=0)
        assert objects.count_objects(root) >= 1
    finally:
        locked.chmod(0o755)


def test_content_at_skips_events_before_revision(root, doc):
    """События до запрошенной ревизии пропускаются: показывается состояние ПОСЛЕ неё."""
    _edit(doc, 9, "первая")
    second = _edit(doc, 10, "вторая")
    _edit(doc, 11, "третья")
    data, status = H.content_at(root, second, "notes/a.md")
    assert status == "ok"
    text = data.decode("utf-8")
    assert "первая" in text and "вторая" in text and "третья" not in text


def test_content_at_object_missing(root, doc):
    first = _edit(doc, 9, "первая")
    _edit(doc, 10, "вторая")
    later = journal.read_events(root)[-1]
    objects.remove_object(root, later["paths"][0]["before"])
    data, status = H.content_at(root, first, "notes/a.md")
    assert data is None and status == "object_missing"


def test_log_skips_events_for_other_paths(root, doc):
    _edit(doc, 9, "правка")
    events, total, _t = H.log(root, path="другой.md")
    assert total == 0 and events == []


def test_before_content_skips_other_paths(root, doc):
    rev = _edit(doc, 9, "правка")
    data, status = H.before_content(root, rev, "другой.md")
    assert data is None and status == "revision_unknown"


def test_blame_skips_other_paths(root, doc):
    _edit(doc, 9, "правка")
    assert H.blame(root, "другой.md") == []


# --- частичные ветки: пропуск событий, границы раздела, обход хранилища -------


def _crafted(root, rev_paths, kind="doc.edit"):
    return journal.append_event(root, {"schema_version": 1, "at": "2026-01-01T00:00:00Z",
                                       "kind": kind, "actor": "cli", "change_id": None,
                                       "paths": rev_paths, "basis": "test"})


def test_content_at_skips_event_without_snapshot_and_head(root, doc):
    """Событие без снимка и без git_head пропускается: берётся следующее."""
    first = _edit(doc, 9, "первая")
    _crafted(root, [{"path": "notes/a.md", "before": None, "after": None,
                     "git_head": None, "ranges": []}])
    _edit(doc, 10, "вторая")
    data, status = H.content_at(root, first, "notes/a.md")
    assert status == "ok"
    assert "первая" in data.decode("utf-8")


def test_content_at_skips_unreadable_git_head(root, doc):
    """git_head есть, но git содержимое не отдаёт — идём дальше по журналу."""
    first = _edit(doc, 9, "первая")
    _crafted(root, [{"path": "notes/a.md", "before": None, "after": None,
                     "git_head": "0" * 40, "ranges": []}])
    _edit(doc, 10, "вторая")
    data, status = H.content_at(root, first, "notes/a.md")
    assert status == "ok"


def test_before_content_reports_no_before_when_git_silent(root, doc):
    rev = _crafted(root, [{"path": "notes/a.md", "before": None, "after": None,
                           "git_head": "0" * 40, "ranges": []}])
    data, status = H.before_content(root, rev, "notes/a.md")
    assert data is None and status == "no_before"


def test_gc_ignores_entries_without_before(root, doc):
    _crafted(root, [{"path": "notes/a.md", "after": "sha256:x", "git_head": None, "ranges": []}])
    result = H.gc(root, dry_run=True)
    assert result["objects_referenced"] == 0 and result["kept_events"] == 1


def test_last_revision_ignores_other_paths(root, doc):
    """Обход журнала пропускает события других файлов и не-словари."""
    _crafted(root, [{"path": "другой.md", "git_head": "0" * 40}, "не словарь"])
    assert H._last_revision_for(FileHistoryStore(root), "notes/a.md") is None


def test_ranges_touch_section_ignores_malformed_ranges(root, sectioned):
    """Мусор в ranges пропускается поштучно, а не роняет фильтр целиком."""
    assert H._ranges_touch_section(root, "s.md", "## Решение", [None, "x", [1]]) is False
    assert H._ranges_touch_section(root, "s.md", "## Решение", [None, [9, 9]]) is True


def test_section_bounds_with_subsection(root):
    """Вложенный подраздел не закрывает раздел: граница — следующий заголовок того же уровня."""
    target = root / "sub.md"
    target.write_text("# Заг\n\n## Решение\n\n### Детали\n\nтекст\n\n## Итоги\n\nконец\n",
                      encoding="utf-8")
    start, end = H._section_bounds(root, "sub.md", "## Решение")
    assert (start, end) == (3, 8)


def test_two_objects_share_prefix_directory(root):
    """Удаление одного объекта не трогает каталог, пока в нём есть сосед."""
    first = objects.write_snapshot(root, "данные".encode("utf-8"))
    prefix = first[len("sha256:"):][:2]
    sibling = objects.objects_dir(root) / prefix / ("f" * 62)
    sibling.write_bytes(b"x")
    assert objects.remove_object(root, first) is True
    assert sibling.is_file()


def test_trim_objects_reports_locked_orphan(root, doc):
    _edit(doc, 9, "правка")
    orphan = objects.write_snapshot(root, "сирота".encode("utf-8"))
    parent = objects.object_path(root, orphan).parent
    parent.chmod(0o555)
    try:
        H.gc(root, keep_objects=0)
        assert objects.count_objects(root) >= 1
    finally:
        parent.chmod(0o755)


def test_configured_backend_rejects_empty_and_non_string():
    assert H.configured_backend({"history": {"backend": ""}}) is None
    assert H.configured_backend({"history": {"backend": 5}}) is None


def test_record_write_skips_snapshot_when_git_reachable(git_repo):
    """Бэкенд git: снимок не нужен, когда прошлое состояние доступно из git."""
    backend = GitBackend(git_repo)
    journal.append_event(git_repo, {"kind": "doc.edit",
                                    "paths": [{"path": "a.md", "git_head": "0" * 40}]})
    rev = H.record_write(git_repo, "a.md", "старое".encode("utf-8"),
                         "новое".encode("utf-8"), kind="doc.edit", backend=backend)
    assert rev and journal.read_events(git_repo)[-1]["paths"][0]["before"] is None


# --- режим observed: внешние правки ------------------------------------------


def test_observed_records_external_change(root, doc):
    """Расхождение хеша без записи журнала фиксируется как external.change."""
    H.adopt(root, [{"path": "notes/a.md"}])
    doc.write_text(doc.read_text(encoding="utf-8") + "внешняя строка\n", encoding="utf-8")
    current = "sha256:" + hashlib.sha256(doc.read_bytes()).hexdigest()
    revs = H.observe_external_changes(root, [("notes/a.md", current)])
    assert len(revs) == 1
    event = journal.read_events(root)[-1]
    assert event["kind"] == H.EXTERNAL_CHANGE
    assert event["actor"] == "external"
    assert event["paths"][0]["after"] == current
    assert event["paths"][0]["before"] is None


def test_observed_is_idempotent(root, doc):
    """Один внешний факт — одно событие: повторный скан ничего не дописывает."""
    H.adopt(root, [{"path": "notes/a.md"}])
    doc.write_text(doc.read_text(encoding="utf-8") + "внешняя строка\n", encoding="utf-8")
    current = "sha256:" + hashlib.sha256(doc.read_bytes()).hexdigest()
    assert len(H.observe_external_changes(root, [("notes/a.md", current)])) == 1
    assert H.observe_external_changes(root, [("notes/a.md", current)]) == []
    assert len(journal.read_events(root)) == 2


def test_observed_without_journal_stays_silent(root, doc):
    """Без базовой линии первый скан не объявляет внешним весь корпус."""
    current = "sha256:" + hashlib.sha256(doc.read_bytes()).hexdigest()
    assert H.observe_external_changes(root, [("notes/a.md", current)]) == []
    assert journal.read_events(root) == []


def test_observed_detects_external_deletion(root, doc):
    H.adopt(root, [{"path": "notes/a.md"}])
    doc.unlink()
    revs = H.observe_external_changes(root, [])
    assert len(revs) == 1
    assert journal.read_events(root)[-1]["paths"][0]["after"] == ""


def test_observed_does_not_report_missing_file_that_never_existed(root, doc):
    H.adopt(root, [{"path": "notes/a.md"}])
    # путь есть в журнале, но на диске он есть — удаления не было, скан его просто не вернул
    assert H.observe_external_changes(root, []) == []


def test_observed_off_by_mode(root, doc):
    H.adopt(root, [{"path": "notes/a.md"}])
    doc.write_text(doc.read_text(encoding="utf-8") + "внешняя\n", encoding="utf-8")
    current = "sha256:" + hashlib.sha256(doc.read_bytes()).hexdigest()
    assert H.observe_external_changes(root, [("notes/a.md", current)], mode="off") == []


def test_observed_skips_non_dict_paths(root, doc):
    H.adopt(root, [{"path": "notes/a.md"}])
    _crafted(root, ["не словарь", {"git_head": "0" * 40}])
    current = "sha256:" + hashlib.sha256(doc.read_bytes()).hexdigest()
    assert H.observe_external_changes(root, [("notes/a.md", current)]) == []


def test_observed_records_file_added_after_baseline(root, doc):
    """После базовой линии новый файл корпуса — внешний факт, а до неё он просто неизвестен."""
    new_hash = "sha256:" + "a" * 64
    # до базовой линии неизвестный путь не помечается
    assert H.observe_external_changes(root, [("notes/a.md", "sha256:" + "b" * 64),
                                             ("notes/new.md", new_hash)]) == []
    H.adopt(root, [{"path": "notes/a.md"}])
    revs = H.observe_external_changes(root, [("notes/new.md", new_hash)])
    assert len(revs) == 1
    event = journal.read_events(root)[-1]
    assert event["kind"] == H.EXTERNAL_CHANGE and event["paths"][0]["path"] == "notes/new.md"


# --- Фаза 2: лимиты хранилища и конфликт отката -------------------------------


def test_events_bytes_matches_journal_on_disk(doc):
    """Потолок ``max_journal_bytes`` сравнивается с теми же байтами, что лежат в файле."""
    _edit(doc, 8, "правка восемь")
    _edit(doc, 9, "правка девять")
    events = journal.read_events(doc.parent.parent)
    on_disk = journal.journal_path(doc.parent.parent).stat().st_size
    assert journal.events_bytes(events) == on_disk


def test_gc_trims_journal_to_max_bytes(doc):
    """Журнал больше потолка: самые старые события уходят, и это сказано в результате."""
    root = doc.parent.parent
    _edit(doc, 8, "правка восемь")
    _edit(doc, 9, "правка девять")
    _edit(doc, 10, "правка десять")
    events = journal.read_events(root)
    two = journal.events_bytes(events[-2:])
    result = H.gc(root, limits={"max_journal_bytes": two})
    assert result["trimmed_for_size"] == 1
    assert result["kept_events"] == 2
    assert journal.events_bytes(journal.read_events(root)) <= two


def test_gc_keeps_journal_when_under_limit(doc):
    root = doc.parent.parent
    _edit(doc, 8, "правка восемь")
    before = len(journal.read_events(root))
    result = H.gc(root, limits={"max_journal_bytes": 10_000_000})
    assert result["trimmed_for_size"] == 0
    assert result["kept_events"] == before


def test_gc_defaults_keep_objects_to_limit(doc):
    """``max_history_objects`` — значение по умолчанию для обрезки снимков."""
    root = doc.parent.parent
    for line in (8, 9, 10):
        _edit(doc, line, f"правка {line}")
    assert objects.count_objects(root) >= 3
    H.gc(root, limits={"max_history_objects": 1})
    assert objects.count_objects(root) == 1


def test_explicit_keep_objects_wins_over_limit(doc):
    """Явный ``keep_objects`` важнее лимита: потолок не отменяет решение вызывающего."""
    root = doc.parent.parent
    for line in (8, 9, 10):
        _edit(doc, line, f"правка {line}")
    H.gc(root, keep_objects=2, limits={"max_history_objects": 0})
    assert objects.count_objects(root) == 2


def test_revert_of_latest_revision_has_no_conflict(doc):
    """Откат последней правки ничего более позднего не стирает."""
    rev = _edit(doc, 8, "правка восемь")
    plan = H.revert_plan(doc.parent.parent, rev, "notes/a.md")
    assert plan["status"] == "ok"
    assert plan["range_conflict"] is False


def test_revert_of_old_revision_reports_range_conflict(doc):
    """Файл менялся после снимаемой ревизии: откат стёр бы более поздние правки."""
    root = doc.parent.parent
    old_rev = _edit(doc, 8, "правка восемь")
    _edit(doc, 9, "правка девять")
    plan = H.revert_plan(root, old_rev, "notes/a.md")
    assert plan["range_conflict"] is True
    assert plan["status"] == "ok", "конфликт — предупреждение, а не отказ"
