"""Фаза 4: якоря derived_from и подтверждение устаревания (K33, K34, K44, K45)."""

import json

import pytest

from todoc.application.staleness import (ACK_AT, ACK_HASHES, ACK_REASON, check_all, check_owner,
                                         collect_owners,
                                         current_hashes, dependencies_of, format_anchor, fragment_hash,
                                         parse_anchor, plan_ack)

BENCH = {"meta": {"date": "2026-11-25", "score": 29.5}, "probes": {"S1": "ok"}}


@pytest.fixture()
def corpus(root):
    """Корпус с одним JSON-источником и одним Markdown-документом о нём."""
    bench = root / "bench" / "results"
    bench.mkdir(parents=True)
    (bench / "benchmark.json").write_text(json.dumps(BENCH, indent=2) + "\n", encoding="utf-8")
    state = root / "docs" / "state"
    state.mkdir(parents=True)
    doc = state / "10-testing.md"
    doc.write_text("---\ntitle: \"Качество\"\n---\n\n# Качество\n\nДата: 2026-11-25.\n", encoding="utf-8")
    return {"root": root, "bench": bench / "benchmark.json", "doc": doc}


def _set(bench, **kw):
    data = json.loads(bench.read_text(encoding="utf-8"))
    for key, value in kw.items():
        section, _, field = key.partition("__")
        data[section][field] = value
    bench.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_anchor(doc, dep, root):
    digest, status = fragment_hash(root, dep)
    assert status == "ok", f"якорь не разрешается до записи: {status}"
    anchor = format_anchor({**dep, "hash": digest})
    doc.write_text(f'---\ntitle: "Качество"\nderived_from: ["{anchor}"]\n---\n\n# Качество\n', encoding="utf-8")


# --- хеш фрагмента ----------------------------------------------------------


def test_fragment_hash_pointer(corpus):
    digest, status = fragment_hash(corpus["root"], {"path": "bench/results/benchmark.json", "pointer": "/meta/date"})
    assert status == "ok" and digest.startswith("sha256:")


def test_fragment_hash_ignores_unrelated_fields(corpus):
    """K44: изменение несвязанного поля не двигает хеш якоря."""
    dep = {"path": "bench/results/benchmark.json", "pointer": "/meta/date"}
    before = fragment_hash(corpus["root"], dep)[0]
    _set(corpus["bench"], probes__S1="changed")
    _set(corpus["bench"], meta__score=30.0)
    assert fragment_hash(corpus["root"], dep)[0] == before


def test_fragment_hash_moves_with_anchored_field(corpus):
    dep = {"path": "bench/results/benchmark.json", "pointer": "/meta/date"}
    before = fragment_hash(corpus["root"], dep)[0]
    _set(corpus["bench"], meta__date="2026-11-26")
    assert fragment_hash(corpus["root"], dep)[0] != before


def test_fragment_hash_whole_file_without_anchor(corpus):
    dep = {"path": "bench/results/benchmark.json"}
    before = fragment_hash(corpus["root"], dep)[0]
    _set(corpus["bench"], probes__S1="changed")
    assert fragment_hash(corpus["root"], dep)[0] != before


def test_fragment_hash_missing_file(corpus):
    digest, status = fragment_hash(corpus["root"], {"path": "nope.json", "pointer": "/x"})
    assert digest is None and status == "missing"


def test_fragment_hash_unresolved_pointer(corpus):
    digest, status = fragment_hash(corpus["root"], {"path": "bench/results/benchmark.json", "pointer": "/meta/nope"})
    assert digest is None and status == "unresolved"


def test_fragment_hash_section(corpus):
    doc = corpus["doc"]
    doc.write_text("# Заголовок\n\n## Решение\n\nтекст решения\n\n## Другое\n\nпрочее\n", encoding="utf-8")
    dep = {"path": "docs/state/10-testing.md", "section": "## Решение"}
    before, status = fragment_hash(corpus["root"], dep)
    assert status == "ok"
    # правка в другом разделе не двигает хеш
    doc.write_text("# Заголовок\n\n## Решение\n\nтекст решения\n\n## Другое\n\nизменилось\n", encoding="utf-8")
    assert fragment_hash(corpus["root"], dep)[0] == before
    # правка в самом разделе двигает
    doc.write_text("# Заголовок\n\n## Решение\n\nдругой текст\n\n## Другое\n\nпрочее\n", encoding="utf-8")
    assert fragment_hash(corpus["root"], dep)[0] != before


def test_fragment_hash_unresolved_section(corpus):
    corpus["doc"].write_text("# Заголовок\n\nтекст\n", encoding="utf-8")
    digest, status = fragment_hash(corpus["root"], {"path": "docs/state/10-testing.md", "section": "## Нет"})
    assert digest is None and status == "unresolved"


# --- якоря ------------------------------------------------------------------


def test_anchor_roundtrip_pointer():
    dep = {"path": "a/b.json", "pointer": "/meta/date", "hash": "sha256:aa"}
    assert parse_anchor(format_anchor(dep)) == dep


def test_anchor_roundtrip_section():
    dep = {"path": "docs/x.md", "section": "## Решение", "hash": "sha256:bb"}
    assert parse_anchor(format_anchor(dep)) == dep


def test_anchor_roundtrip_whole_file():
    dep = {"path": "docs/x.md", "hash": "sha256:cc"}
    assert parse_anchor(format_anchor(dep)) == dep


def test_parse_anchor_rejects_garbage():
    assert parse_anchor("просто строка") is None
    assert parse_anchor("a.md@sha256:") == {"path": "a.md", "hash": "sha256:"}
    assert parse_anchor("a.md#непонятно@sha256:aa") is None
    assert parse_anchor("@sha256:aa") is None


def test_dependencies_of_accepts_objects_and_strings():
    owner = {"derived_from": [{"path": "a.json", "pointer": "/x", "hash": "sha256:1"},
                              "b.md#section:## Y@sha256:2", "мусор"]}
    deps = dependencies_of(owner)
    assert len(deps) == 2
    assert deps[0]["path"] == "a.json" and deps[1]["section"] == "## Y"


# --- диагностика владельца ---------------------------------------------------


def _owner(doc):
    from todoc.adapters.formats.markdown import parse_markdown
    return parse_markdown(doc.read_text(encoding="utf-8")).front_matter


def test_no_drift_gives_no_diagnostics(corpus):
    """K34: на неизменном корпусе ложных срабатываний нет."""
    dep = {"path": "bench/results/benchmark.json", "pointer": "/meta/date"}
    _write_anchor(corpus["doc"], dep, corpus["root"])
    assert check_owner("ds", "docs/state/10-testing.md", _owner(corpus["doc"]), corpus["root"]) == []


def test_drift_is_reported(corpus):
    """K33: расхождение заякоренного поля обнаруживается."""
    dep = {"path": "bench/results/benchmark.json", "pointer": "/meta/date"}
    _write_anchor(corpus["doc"], dep, corpus["root"])
    _set(corpus["bench"], meta__date="2026-11-26")
    diags = check_owner("ds", "docs/state/10-testing.md", _owner(corpus["doc"]), corpus["root"])
    assert [d.code for d in diags] == ["staleness.dependency_changed"]
    assert diags[0].severity == "warning"


def test_missing_dependency_reported_separately(corpus):
    dep = {"path": "bench/results/benchmark.json", "pointer": "/meta/date"}
    _write_anchor(corpus["doc"], dep, corpus["root"])
    corpus["bench"].unlink()
    diags = check_owner("ds", "docs/state/10-testing.md", _owner(corpus["doc"]), corpus["root"])
    assert [d.code for d in diags] == ["staleness.dependency_missing"]


def test_diagnostic_ids_are_stable(corpus):
    dep = {"path": "bench/results/benchmark.json", "pointer": "/meta/date"}
    _write_anchor(corpus["doc"], dep, corpus["root"])
    _set(corpus["bench"], meta__date="2026-11-26")
    first = check_owner("ds", "docs/state/10-testing.md", _owner(corpus["doc"]), corpus["root"])[0].id
    second = check_owner("ds", "docs/state/10-testing.md", _owner(corpus["doc"]), corpus["root"])[0].id
    assert first == second


# --- подтверждение -----------------------------------------------------------


def test_ack_suppresses_and_lapses(corpus):
    """K45: подтверждение снимает диагностику, смена хеша возвращает её."""
    dep = {"path": "bench/results/benchmark.json", "pointer": "/meta/date"}
    _write_anchor(corpus["doc"], dep, corpus["root"])
    _set(corpus["bench"], meta__date="2026-11-26")
    owner = {"source": _owner(corpus["doc"])}
    assert len(check_owner("ds", "p", owner["source"], corpus["root"])) == 1

    hashes = current_hashes(corpus["root"], owner)
    text = plan_ack(corpus["root"], "docs/state/10-testing.md", "не релевантно", "2026-11-25T00:00:00Z", hashes)
    corpus["doc"].write_text(text, encoding="utf-8")
    assert check_owner("ds", "docs/state/10-testing.md", _owner(corpus["doc"]), corpus["root"]) == []

    _set(corpus["bench"], meta__date="2026-11-27")
    diags = check_owner("ds", "docs/state/10-testing.md", _owner(corpus["doc"]), corpus["root"])
    assert [d.code for d in diags] == ["staleness.dependency_changed"]


def test_plan_ack_preserves_body(corpus):
    corpus["doc"].write_text('---\ntitle: "Качество"\n---\n\n# Качество\n\nТело документа.\n', encoding="utf-8")
    text = plan_ack(corpus["root"], "docs/state/10-testing.md", "причина", "2026-11-25T00:00:00Z", ["sha256:aa"])
    assert "# Качество\n\nТело документа." in text
    assert ACK_AT in text and ACK_REASON in text and ACK_HASHES in text


def test_plan_ack_replaces_previous_ack(corpus):
    corpus["doc"].write_text('---\ntitle: "К"\n---\n\nтело\n', encoding="utf-8")
    once = plan_ack(corpus["root"], "docs/state/10-testing.md", "первая", "2026-11-25T00:00:00Z", ["sha256:aa"])
    corpus["doc"].write_text(once, encoding="utf-8")
    twice = plan_ack(corpus["root"], "docs/state/10-testing.md", "вторая", "2026-11-26T00:00:00Z", ["sha256:bb"])
    assert twice.count(ACK_AT + ":") == 1
    assert "вторая" in twice and "первая" not in twice


def test_plan_ack_without_front_matter_raises(corpus):
    corpus["doc"].write_text("# Просто заголовок\n", encoding="utf-8")
    with pytest.raises(ValueError):
        plan_ack(corpus["root"], "docs/state/10-testing.md", "причина", "2026-11-25T00:00:00Z", ["sha256:aa"])


# --- сквозная проверка по индексу --------------------------------------------


def test_check_all_finds_seeded_drift(root, corpus):
    """K33 на десяти засеянных расхождениях: recall должен быть 1.0."""
    from todoc.service import DatasetContext

    anchors = []
    for i in range(10):
        src = root / "src"
        src.mkdir(exist_ok=True)
        (src / f"s{i}.json").write_text(json.dumps({"v": i}) + "\n", encoding="utf-8")
        dep = {"path": f"src/s{i}.json", "pointer": "/v"}
        anchors.append(format_anchor({**dep, "hash": fragment_hash(root, dep)[0]}))
    owner_doc = root / "owner.md"
    listing = ", ".join(f'"{a}"' for a in anchors)
    owner_doc.write_text(f'---\ntitle: "Владелец"\nderived_from: [{listing}]\n---\n\n# Владелец\n', encoding="utf-8")

    ctx = DatasetContext(root)
    payload = ctx.ensure_index()
    assert check_all("ds", root, payload) == []

    for i in range(10):
        (root / "src" / f"s{i}.json").write_text(json.dumps({"v": i + 100}) + "\n", encoding="utf-8")
    payload = ctx.ensure_index()
    diags = check_all("ds", root, payload)
    assert len(diags) == 10
    assert all(d.code == "staleness.dependency_changed" for d in diags)


def test_check_all_filters_by_path(root, corpus):
    from todoc.service import DatasetContext

    dep = {"path": "bench/results/benchmark.json", "pointer": "/meta/date"}
    _write_anchor(corpus["doc"], dep, corpus["root"])
    _set(corpus["bench"], meta__date="2026-11-26")
    ctx = DatasetContext(root)
    payload = ctx.ensure_index()
    assert len(check_all("ds", root, payload, only_path="docs/state/10-testing.md")) == 1
    assert check_all("ds", root, payload, only_path="нет/такого.md") == []


# --- покрытие веток ошибок ---------------------------------------------------


def test_fragment_hash_unreadable_file(corpus):
    target = corpus["root"] / "binary.json"
    target.write_bytes(b"\xff\xfe\x00\x01")
    digest, status = fragment_hash(corpus["root"], {"path": "binary.json"})
    assert digest is None and status == "unreadable"


def test_fragment_hash_invalid_json_is_unresolved(corpus):
    corpus["bench"].write_text("{ не json", encoding="utf-8")
    digest, status = fragment_hash(corpus["root"], {"path": "bench/results/benchmark.json", "pointer": "/meta"})
    assert digest is None and status == "unresolved"


def test_parse_anchor_requires_sha256_digest():
    assert parse_anchor("a.md@md5:aa") is None
    assert parse_anchor(123) is None


def test_ack_hashes_accepts_plain_string():
    from todoc.application.staleness import _ack_hashes
    assert _ack_hashes({ACK_HASHES: "sha256:aa"}) == {"sha256:aa"}
    assert _ack_hashes({ACK_HASHES: ""}) == set()
    assert _ack_hashes({}) == set()


def test_unresolved_anchor_is_reported(corpus):
    """Якорь есть, но указатель исчез — это отдельное сообщение, чем смена хеша."""
    dep = {"path": "bench/results/benchmark.json", "pointer": "/meta/date"}
    _write_anchor(corpus["doc"], dep, corpus["root"])
    corpus["bench"].write_text(json.dumps({"meta": {"score": 1}}) + "\n", encoding="utf-8")
    diags = check_owner("ds", "docs/state/10-testing.md", _owner(corpus["doc"]), corpus["root"])
    assert [d.code for d in diags] == ["staleness.dependency_changed"]
    assert "не разрешается" in diags[0].message


def test_collect_owners_skips_unreadable_document(root, corpus):
    from todoc.service import DatasetContext

    corpus["doc"].write_text('---\ntitle: "К"\nderived_from: ["a.json@sha256:aa"]\n---\n\nтело\n', encoding="utf-8")
    ctx = DatasetContext(root)
    payload = ctx.ensure_index()
    owners = collect_owners(root, payload)
    assert [o["path"] for o in owners] == ["docs/state/10-testing.md"]


def test_collect_owners_includes_records(root):
    from todoc.service import DatasetContext

    records = root / "records" / "task"
    records.mkdir(parents=True)
    (records / "t1.json").write_text(json.dumps({
        "record_id": "task:t1", "entity_type": "task",
        "derived_from": [{"path": "a.json", "pointer": "/v", "hash": "sha256:aa"}],
    }) + "\n", encoding="utf-8")
    (root / "a.json").write_text(json.dumps({"v": 1}) + "\n", encoding="utf-8")
    ctx = DatasetContext(root)
    payload = ctx.ensure_index()
    owners = collect_owners(root, payload)
    kinds = {o["path"]: o["kind"] for o in owners}
    assert kinds.get("records/task/t1.json") == "record"
    diags = check_all("ds", root, payload)
    assert [d.code for d in diags] == ["staleness.dependency_changed"]


def test_plan_ack_rejects_unclosed_front_matter(corpus):
    corpus["doc"].write_text('---\ntitle: "К"\n\n# без закрывающей черты\n', encoding="utf-8")
    with pytest.raises(ValueError):
        plan_ack(corpus["root"], "docs/state/10-testing.md", "причина", "2026-11-25T00:00:00Z", ["sha256:aa"])


def test_collect_owners_skips_binary_document(root, corpus):
    from todoc.service import DatasetContext

    (root / "broken.md").write_bytes(b"\xff\xfe\x00\x01binary")
    ctx = DatasetContext(root)
    payload = ctx.ensure_index()
    assert "broken.md" not in [o["path"] for o in collect_owners(root, payload)]


def test_collect_owners_ignores_record_without_dependencies(root):
    from todoc.service import DatasetContext

    records = root / "records" / "task"
    records.mkdir(parents=True)
    (records / "plain.json").write_text(json.dumps({"record_id": "task:p", "entity_type": "task"}) + "\n",
                                        encoding="utf-8")
    ctx = DatasetContext(root)
    payload = ctx.ensure_index()
    assert collect_owners(root, payload) == []


def test_section_hash_of_last_section(corpus):
    """Якорь на последний раздел: цикла-ограничителя нет, граница — конец файла."""
    doc = corpus["doc"]
    doc.write_text("# Заголовок\n\n## Решение\n\nтекст решения\n", encoding="utf-8")
    dep = {"path": "docs/state/10-testing.md", "section": "## Решение"}
    before, status = fragment_hash(corpus["root"], dep)
    assert status == "ok"
    doc.write_text("# Заголовок\n\n## Решение\n\nдругой текст\n", encoding="utf-8")
    assert fragment_hash(corpus["root"], dep)[0] != before


def test_section_hash_stops_at_same_level_after_deeper_headings(corpus):
    """Вложенные подзаголовки глубже не закрывают раздел — только заголовок того же уровня."""
    doc = corpus["doc"]
    first = "# З\n\n## Решение\n\nтекст\n\n### Подробности\n\nдетали\n\n## Другое\n\nпрочее\n"
    doc.write_text(first, encoding="utf-8")
    dep = {"path": "docs/state/10-testing.md", "section": "## Решение"}
    before, _ = fragment_hash(corpus["root"], dep)
    # правка внутри вложенного подраздела относится к якорному разделу
    doc.write_text(first.replace("детали", "изменённые детали"), encoding="utf-8")
    assert fragment_hash(corpus["root"], dep)[0] != before
    # правка в следующем разделе того же уровня — уже нет
    doc.write_text(first.replace("прочее", "изменённое прочее"), encoding="utf-8")
    assert fragment_hash(corpus["root"], dep)[0] == before


def test_dependencies_of_rejects_non_list():
    assert dependencies_of({"derived_from": "a.md@sha256:aa"}) == []
    assert dependencies_of({}) == []
    assert dependencies_of({"derived_from": None}) == []


def test_dependencies_of_skips_items_that_are_neither():
    owner = {"derived_from": [{"без_path": 1}, 42, None, "a.md@sha256:aa"]}
    deps = dependencies_of(owner)
    assert len(deps) == 1 and deps[0]["path"] == "a.md"
