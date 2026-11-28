"""Unit tests for the CLI helpers added while hardening the benchmark results."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from todoc.cli import SECTION_MAX_LINES, _contained_out, _parse_line_range, _parse_offset, cli
from todoc.errors import AccessError, TodocError, ValidationError


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


# --- _parse_offset -----------------------------------------------------------


def test_parse_offset_defaults_to_zero():
    assert _parse_offset(None) == 0
    assert _parse_offset("") == 0


def test_parse_offset_accepts_an_integer():
    assert _parse_offset("20") == 20


def test_parse_offset_rejects_garbage():
    with pytest.raises(ValidationError) as exc:
        _parse_offset("abc")
    assert exc.value.code == "usage.invalid_cursor"


def test_parse_offset_rejects_negative():
    with pytest.raises(ValidationError) as exc:
        _parse_offset("-1")
    assert exc.value.code == "usage.invalid_cursor"


# --- _parse_line_range -------------------------------------------------------


def test_parse_line_range_single_line():
    assert _parse_line_range("7") == (7, 7)


def test_parse_line_range_span():
    assert _parse_line_range("7-12") == (7, 12)


def test_parse_line_range_open_ended():
    assert _parse_line_range("7-") == (7, 7)


def test_parse_line_range_rejects_garbage():
    with pytest.raises(ValidationError) as exc:
        _parse_line_range("abc")
    assert exc.value.code == "usage.invalid_line_range"


def test_parse_line_range_rejects_zero_and_reversed():
    for bad in ("0", "0-3", "9-4"):
        with pytest.raises(ValidationError) as exc:
            _parse_line_range(bad)
        assert exc.value.code == "usage.invalid_line_range"


# --- _contained_out ----------------------------------------------------------


def test_contained_out_resolves_relative_paths(root):
    out = _contained_out(root, ".todoc/guide.md")
    assert out == (root / ".todoc" / "guide.md").resolve()


def test_contained_out_rejects_absolute_escape(root, tmp_path):
    with pytest.raises(AccessError) as exc:
        _contained_out(root, str(tmp_path / "escaped.md"))
    assert exc.value.code == "access.outside_data_root"
    assert exc.value.exit_code == 4


def test_contained_out_rejects_relative_escape(root):
    with pytest.raises(AccessError):
        _contained_out(root, "../../escaped.md")


# --- docs read --section -----------------------------------------------------


def _section(root, doc_id, title):
    result = _run(CliRunner(), ["--root", str(root), "docs", "read", "--id", doc_id,
                                "--section", title, "--output", "json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["data"]["result"]


@pytest.fixture()
def sections_root(root):
    (root / "notes").mkdir(parents=True, exist_ok=True)
    body = ["# Top", "", "intro", "", "## Alpha", "", "alpha body", "",
            "### Alpha deep", "", "deep body", "", "## Beta", "", "beta body", ""]
    (root / "notes" / "sections.md").write_text("\n".join(body), encoding="utf-8")
    return root


def test_section_stops_at_the_next_sibling(sections_root):
    data = _section(sections_root, "doc:notes/sections.md", "Alpha")
    assert data["truncated"] is False
    assert not any(line.startswith("## Beta") for line in data["lines"])
    # a deeper heading belongs to the section and is kept
    assert any(line.startswith("### Alpha deep") for line in data["lines"])
    assert data["heading_path"] == ["Top", "Alpha"]


def test_last_section_runs_to_end_of_file(sections_root):
    data = _section(sections_root, "doc:notes/sections.md", "Beta")
    assert data["heading_path"] == ["Top", "Beta"]
    assert "beta body" in data["lines"]


def test_key_location_empty_and_missing_key():
    from todoc.application.validator import _key_location

    text = '{\n  "record_id": "x"\n}\n'
    assert _key_location(text, "") == {}
    assert _key_location(text, "absent") == {}
    assert _key_location(text, "record_id") == {"line": 2, "column": 3}


def test_section_window_is_capped(sections_root):
    long_body = ["## Big", ""] + [f"line {i}" for i in range(120)]
    (sections_root / "notes" / "big.md").write_text("\n".join(long_body), encoding="utf-8")
    data = _section(sections_root, "doc:notes/big.md", "Big")
    assert len(data["lines"]) == SECTION_MAX_LINES
    assert data["truncated"] is True
    assert data["line_end"] == data["line_start"] + SECTION_MAX_LINES - 1
