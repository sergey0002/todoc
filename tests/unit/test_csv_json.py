import pytest

from todoc.adapters.formats.csvfmt import parse_csv
from todoc.adapters.formats.jsonfmt import parse_json, resolve_pointer


def test_csv_comma():
    doc = parse_csv("a,b\n1,2\n3,4\n")
    assert doc.headers == ["a", "b"]
    assert doc.rows == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
    assert doc.errors == []


def test_csv_semicolon_and_tab():
    assert parse_csv("a;b\n1;2\n").dialect == "semicolon"
    assert parse_csv("a\tb\n1\t2\n").dialect == "tab"


def test_csv_bom():
    doc = parse_csv("\ufeffa,b\n1,2\n")
    assert doc.headers == ["a", "b"]


def test_csv_duplicate_header():
    doc = parse_csv("a,a\n1,2\n")
    assert any("duplicate_header" in e for e in doc.errors)


def test_csv_wrong_width():
    doc = parse_csv("a,b\n1\n")
    assert any("wrong_width" in e for e in doc.errors)


def test_csv_empty():
    doc = parse_csv("")
    assert doc.errors == ["csv.empty"]


def test_csv_missing_header():
    doc = parse_csv(",\n1,2\n")
    assert any("missing_header" in e for e in doc.errors)


def test_csv_quoted_newline():
    doc = parse_csv('a,b\n"x\ny",2\n')
    assert doc.rows[0]["a"] == "x\ny"


def test_csv_too_many_rows():
    doc = parse_csv("a\n1\n2\n3\n", max_rows=2)
    assert any("too_many_rows" in e for e in doc.errors)


def test_json_ok():
    value, errors = parse_json('{"a": 1}')
    assert value == {"a": 1}
    assert errors == []


def test_json_syntax_error():
    value, errors = parse_json("{bad")
    assert value is None
    assert any("syntax_error" in e for e in errors)


def test_json_duplicate_key():
    value, errors = parse_json('{"a": 1, "a": 2}')
    assert value is None
    assert any("duplicate_key" in e for e in errors)


def test_json_too_deep():
    deep = "[" * 200 + "]" * 200
    value, errors = parse_json(deep, max_depth=10)
    assert value is None
    assert errors == ["json.too_deep"]


def test_pointer():
    value = {"a": {"b": [10, 20]}}
    assert resolve_pointer(value, "/a/b/1") == 20
    assert resolve_pointer(value, "") == value
    assert resolve_pointer(value, "/") == value
    with pytest.raises(KeyError):
        resolve_pointer(value, "/missing")
    with pytest.raises(KeyError):
        resolve_pointer(value, "bad")
    with pytest.raises((IndexError, ValueError)):
        resolve_pointer(value, "/a/b/9")
