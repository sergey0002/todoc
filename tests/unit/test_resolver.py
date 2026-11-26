from todoc.typing_system.resolver import RESERVED_DIR_TYPES, glob_match, glob_to_regex, literal_segments, resolve_type


def test_glob_star_does_not_cross_slash():
    assert glob_match("*.md", "a.md")
    assert not glob_match("*.md", "sub/a.md")


def test_glob_double_star_zero_or_more():
    assert glob_match("**/plan", "plan")
    assert glob_match("**/plan", "a/b/plan")
    assert glob_match("**/*.md", "a.md")
    assert glob_match("**/*.md", "x/y/a.md")


def test_glob_question_and_leading_slash():
    assert glob_match("/a?.md", "ab.md")
    assert not glob_match("/a?.md", "a/b.md")


def test_glob_to_regex_compiles():
    assert glob_to_regex("a/b").match("a/b")
    assert not glob_to_regex("a/b").match("a/c")


def test_literal_segments():
    assert literal_segments("**/adr/*.md") == 1
    assert literal_segments("a/b/c") == 3


def test_resolve_by_glob_rule():
    rules = [{"id": "r1", "match": {"kind": "file", "glob": "**/adr/*.md"}, "assign": {"doc_type": "adr"}, "priority": 50}]
    doc_type, source, conflicts = resolve_type(rules, "x/adr/a.md", "a.md", None, "doc_type", {}, "unknown")
    assert doc_type == "adr"
    assert source == "rule:r1"
    assert conflicts == []


def test_resolve_by_front_matter():
    rules = [{"id": "g", "match": {"kind": "file", "front_matter": {"doc_type": "glossary-entry"}}, "assign": {"doc_type": "glossary-entry"}, "priority": 200}]
    doc_type, source, _ = resolve_type(rules, "x.md", "x.md", {"doc_type": "glossary-entry"}, "doc_type", {}, "unknown")
    assert doc_type == "glossary-entry"
    assert source == "rule:g"


def test_resolve_front_matter_miss():
    """BUG-001: явный doc_type в front matter выше правил датасета — «other» резолвится как объявлено."""
    rules = [{"id": "g", "match": {"kind": "file", "front_matter": {"doc_type": "glossary-entry"}}, "assign": {"doc_type": "glossary-entry"}, "priority": 200}]
    doc_type, source, _ = resolve_type(rules, "x.md", "x.md", {"doc_type": "other"}, "doc_type", {}, "unknown")
    assert doc_type == "other"
    assert source == "front-matter"


def test_resolve_rule_agreeing_with_explicit_keeps_rule_source():
    """Явное объявление совпало с fm-правилом — значение то же, источник остаётся правилом."""
    rules = [{"id": "g", "match": {"kind": "file", "front_matter": {"doc_type": "note"}}, "assign": {"doc_type": "note"}, "priority": 200}]
    doc_type, source, _ = resolve_type(rules, "x.md", "x.md", {"doc_type": "note"}, "doc_type", {}, "unknown")
    assert (doc_type, source) == ("note", "rule:g")


def test_resolve_reserved():
    doc_type, source, _ = resolve_type([], "a/plan", "plan", None, "dir_type", RESERVED_DIR_TYPES, "unknown")
    assert doc_type == "plan"
    assert source == "reserved"


def test_resolve_default():
    doc_type, source, _ = resolve_type([], "a/b.md", "b.md", None, "doc_type", {}, "unknown")
    assert doc_type == "unknown"
    assert source == "default"


def test_resolve_priority_wins():
    rules = [
        {"id": "low", "match": {"kind": "file", "glob": "**/*.md"}, "assign": {"doc_type": "note"}, "priority": 10},
        {"id": "high", "match": {"kind": "file", "glob": "**/adr/*.md"}, "assign": {"doc_type": "adr"}, "priority": 50},
    ]
    doc_type, source, _ = resolve_type(rules, "x/adr/a.md", "a.md", None, "doc_type", {}, "unknown")
    assert doc_type == "adr"
    assert source == "rule:high"


def test_resolve_tie_ambiguous():
    rules = [
        {"id": "a", "match": {"kind": "file", "glob": "**/*.md"}, "assign": {"doc_type": "note"}, "priority": 10},
        {"id": "b", "match": {"kind": "file", "glob": "**/*.md"}, "assign": {"doc_type": "adr"}, "priority": 10},
    ]
    doc_type, source, conflicts = resolve_type(rules, "x.md", "x.md", None, "doc_type", {}, "unknown")
    assert doc_type == "unknown"
    assert source == "ambiguous"
    assert sorted(conflicts) == ["a", "b"]


def test_resolve_tie_same_assign_ok():
    rules = [
        {"id": "a", "match": {"kind": "file", "glob": "**/*.md"}, "assign": {"doc_type": "note"}, "priority": 10},
        {"id": "b", "match": {"kind": "file", "glob": "**/*.md"}, "assign": {"doc_type": "note"}, "priority": 10},
    ]
    doc_type, source, conflicts = resolve_type(rules, "x.md", "x.md", None, "doc_type", {}, "unknown")
    assert doc_type == "note"
    assert conflicts == []


def test_resolve_directory_basename():
    rules = [{"id": "d", "match": {"kind": "directory", "basename": ".research"}, "assign": {"dir_type": "research"}, "priority": 100}]
    dir_type, source, _ = resolve_type(rules, "a/.research", ".research", None, "dir_type", {}, "unknown")
    assert dir_type == "research"
    assert source == "rule:d"


def test_resolve_directory_glob():
    rules = [{"id": "d", "match": {"kind": "directory", "glob": "**/plan"}, "assign": {"dir_type": "plan"}, "priority": 100}]
    dir_type, source, _ = resolve_type(rules, "a/plan", "plan", None, "dir_type", {}, "unknown")
    assert dir_type == "plan"
    assert source == "rule:d"


def test_resolve_unknown_kind_no_match():
    rules = [{"id": "x", "match": {"kind": "other"}, "assign": {"doc_type": "note"}, "priority": 1}]
    doc_type, source, _ = resolve_type(rules, "x.md", "x.md", None, "doc_type", {}, "unknown")
    assert doc_type == "unknown"
    assert source == "default"
