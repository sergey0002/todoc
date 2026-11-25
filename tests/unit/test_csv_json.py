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
    assert errors == ["json.too_deep: nesting depth 199 exceeds limit 10"]


def test_pointer():
    value = {"a": {b: [10, 20] for b in ("b",)} , "": "empty-key"}
    assert resolve_pointer(value, "/a/b/1") == 20
    assert resolve_pointer(value, "") == value
    # RFC 6901: "/" is the member with the empty-string key, not the document.
    assert resolve_pointer(value, "/") == "empty-key"
    with pytest.raises(KeyError):
        resolve_pointer(value, "/missing")
    with pytest.raises(KeyError):
        resolve_pointer(value, "bad")
    with pytest.raises((IndexError, ValueError)):
        resolve_pointer(value, "/a/b/9")
    # Non-canonical array indices and past-the-end are misses.
    with pytest.raises(KeyError):
        resolve_pointer(value, "/a/b/01")
    with pytest.raises(KeyError):
        resolve_pointer(value, "/a/b/-")
    # Tilde escapes.
    assert resolve_pointer({"a/b": 1, "c~d": 2}, "/a~1b") == 1
    assert resolve_pointer({"a/b": 1, "c~d": 2}, "/c~0d") == 2


# --- P1-8 / K7: позиции у JSON-диагностик -----------------------------------


def test_duplicate_key_reports_line_and_column():
    text = '{\n  "a": 1,\n  "b": 2,\n  "a": 3\n}\n'
    _value, errors = parse_json(text)
    err = errors[0]
    assert err.code == "json.duplicate_key"
    # Второе вхождение "a" — строка 4, колонка 3.
    assert (err.line, err.column) == (4, 3)
    assert text.splitlines()[3][2:5] == '"a"'


def test_duplicate_key_position_is_scoped_to_its_object():
    text = '{\n  "x": {"a": 1},\n  "y": {"a": 2, "a": 3}\n}\n'
    _value, errors = parse_json(text)
    err = errors[0]
    # Повтор — во втором вложенном объекте, а не в первом.
    assert (err.line, err.column) == (3, 17)


def test_duplicate_key_ignores_other_duplicates():
    text = '{"a": 1, "a": 2, "b": 3, "b": 4}'
    _value, errors = parse_json(text)
    # Парсер жалуется на первый повтор; позиция указывает именно его.
    assert errors[0].column == 10


def test_invalid_constant_reports_position():
    cases = [("[NaN]\n", 1, 2), ('{"b": Infinity}\n', 1, 7), ('{"b": -Infinity}\n', 1, 7)]
    for text, line, column in cases:
        _value, errors = parse_json(text)
        err = errors[0]
        assert err.code == "json.invalid_constant", text
        assert (err.line, err.column) == (line, column), text


def test_too_deep_reports_where_limit_was_exceeded():
    text = "[\n" * 3 + "[" * 20 + "]" * 20 + "\n]" * 3
    _value, errors = parse_json(text, max_depth=4)
    err = errors[0]
    assert err.code == "json.too_deep"
    assert err.line is not None and err.column is not None


def test_too_deep_via_recursion_limit_still_located():
    """Глубокий вход роняет парсер в RecursionError — позиция всё равно нужна."""
    text = "[" * 400 + "]" * 400
    _value, errors = parse_json(text)
    err = errors[0]
    assert err.code == "json.too_deep"
    assert err.line == 1 and err.column == 130


def test_positions_survive_multiline_input():
    text = '[\n  1,\n  NaN\n]\n'
    _value, errors = parse_json(text)
    assert (errors[0].line, errors[0].column) == (3, 3)


def test_scanner_never_raises_on_hostile_input():
    from todoc.adapters.formats.jsonfmt import _iter_tokens
    hostile = [
        '"незакрытая строка',          # обрыв строки
        '"a\\',                        # обрыв экранирования
        '}}}[[[',                      # лишние закрывающие
        '{"a" 1}',                     # строка без двоеточия
        '- - -',                       # мусорные числа
        '"\\q\\z"',                    # неразбираемые экранирования
        '\x00\x01',                    # управляющие символы
        'tru fals nul NaN Infinity',   # голые слова
        '',                            # пусто
    ]
    for text in hostile:
        assert isinstance(list(_iter_tokens(text)), list), text


def test_scanner_token_kinds():
    from todoc.adapters.formats.jsonfmt import _iter_tokens
    kinds = [(k, p) for k, p, _o in _iter_tokens('{"k": [1, -2.5e3, "s", true], "k2": {}}')]
    assert ("key", "k") in kinds
    assert ("string", "s") in kinds          # строка-значение, а не ключ
    assert ("number", "-2.5e3") in kinds
    assert ("const", "true") in kinds
    assert ("open", "[") in kinds and ("close", "}") in kinds


def test_duplicate_key_offset_helpers_cover_edge_cases():
    from todoc.adapters.formats.jsonfmt import _constant_offset, _depth_limit_offset, _duplicate_key_offset
    # Лишняя закрывающая скобка и ключ вне объекта не роняют поиск.
    assert _duplicate_key_offset('} "a": 1', "a") is None
    assert _duplicate_key_offset('{"a": 1}', "a") is None
    assert _duplicate_key_offset('{"a": 1, "a": 2}', "нет") is None
    assert _constant_offset("[1]", "NaN") is None
    assert _depth_limit_offset("[[[]]]", 10) is None
    assert _depth_limit_offset("]", 1) is None


def test_located_without_offset_has_no_position():
    from todoc.adapters.formats.jsonfmt import JsonError, _located
    err = _located("{}", "json.duplicate_key", "сообщение", None)
    assert isinstance(err, JsonError)
    assert err.line is None and err.column is None
    assert str(err) == "json.duplicate_key: сообщение"


def test_line_col_helper():
    from todoc.adapters.formats.jsonfmt import _line_col
    assert _line_col("abc\ndef\nghi", 0) == (1, 1)
    assert _line_col("abc\ndef\nghi", 4) == (2, 1)
    assert _line_col("abc\ndef\nghi", 6) == (2, 3)
    assert _line_col("abc\ndef\nghi", 8) == (3, 1)


def test_scanner_consumed_past_a_constant():
    """Полный проход: потребитель не бросает генератор на первой лексеме."""
    from todoc.adapters.formats.jsonfmt import _iter_tokens
    kinds = [(kind, payload) for kind, payload, _offset in _iter_tokens('[-Infinity, 1, "s"]')]
    assert ("const", "-Infinity") in kinds
    assert ("number", "1") in kinds
    assert ("string", "s") in kinds


def test_depth_limit_ignores_non_bracket_tokens():
    from todoc.adapters.formats.jsonfmt import _depth_limit_offset
    assert _depth_limit_offset('[1, "a", NaN, {"k": 2}]', 10) is None
    # Тот же текст, но лимит ниже — позиция находится.
    assert _depth_limit_offset('[1, [2, [3]]]', 1) is not None
