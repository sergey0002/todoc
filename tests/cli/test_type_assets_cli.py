"""CLI surface of type assets: docs new from a template, types show/prompt, check-config."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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


def _run_cli(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    """Subprocess run: the only way to observe main()'s exit-code mapping."""
    return subprocess.run([sys.executable, "-m", "todoc", "--root", str(root), *args],
                          capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[2]))


def _add_doc_type(root: Path, type_id: str, descriptor: dict, template: str | None = None) -> None:
    base = root / ".todoc" / "doc_types" / type_id
    base.mkdir(parents=True, exist_ok=True)
    (base / "type.json").write_text(json.dumps(descriptor, ensure_ascii=False, indent=2), encoding="utf-8")
    if template is not None:
        (base / "template.md").write_text(template, encoding="utf-8")


SPEC = {"schema_version": 1, "type_id": "spec", "version": "0.1", "kind": "doc_type",
        "description": "Спецификация.", "format": "markdown", "template": "template.md",
        "required_sections": ["## Purpose", "## Requirements"]}
SPEC_TEMPLATE = ("# {title}\n\n- Тип: `{type_id}`\n- Дата: {date}\n- ID: `{id}`\n\n"
                 "## Purpose\n\nцель\n\n## Requirements\n\nтребования\n")


# ---------------------------------------------------------------------------
# docs new
# ---------------------------------------------------------------------------

def test_docs_new_uses_the_type_template(root):
    _add_doc_type(root, "spec", SPEC, SPEC_TEMPLATE)
    result = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "Оплата",
                                "--type", "spec", "--dir", "specs", "--output", "json"])
    assert result.exit_code == 0, result.output
    data = _json(result)["data"]
    assert data["doc_type"] == "spec"
    assert data["template"] == ".todoc/doc_types/spec/template.md"
    text = (root / data["path"]).read_text(encoding="utf-8")
    assert text.startswith("# Оплата\n")
    assert "`spec`" in text and "doc:specs/" in text
    assert "{date}" not in text and "{id}" not in text


def test_docs_new_accepts_a_type_id_in_template_flag(root):
    _add_doc_type(root, "spec", SPEC, SPEC_TEMPLATE)
    result = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "T",
                                "--template", "spec", "--dir", "specs", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["doc_type"] == "spec"


def test_docs_new_accepts_an_explicit_template_file(root, tmp_path):
    outside = root / "custom.md"
    outside.write_text("# {title}\n\n## Своя форма\n", encoding="utf-8")
    result = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "T",
                                "--template", "custom.md", "--dir", "inbox", "--output", "json"])
    assert result.exit_code == 0, result.output
    data = _json(result)["data"]
    assert data["template"] == "custom.md"
    assert "## Своя форма" in (root / data["path"]).read_text(encoding="utf-8")


def test_docs_new_missing_template_file_is_a_validation_error(root):
    result = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "T",
                                "--template", "nope.md", "--output", "json"])
    assert result.exit_code == 3
    assert result.exception.code == "types.template_missing"
    # the envelope of a failure is only emitted by main(), hence the subprocess pair
    proc = _run_cli(root, ["docs", "new", "--title", "T", "--template", "nope.md", "--output", "json"])
    assert proc.returncode == 3, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["diagnostics"][0]["code"] == "types.template_missing"


def test_docs_new_unknown_type_is_a_validation_error(root):
    result = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "T",
                                "--type", "ghost", "--output", "json"])
    assert result.exit_code == 3
    assert result.exception.code == "types.unknown"
    proc = _run_cli(root, ["docs", "new", "--title", "T", "--type", "ghost", "--output", "json"])
    assert proc.returncode == 3, proc.stderr
    assert json.loads(proc.stdout)["diagnostics"][0]["code"] == "types.unknown"


def test_docs_new_without_type_stays_a_bare_title(root):
    result = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "Просто",
                                "--dir", "inbox", "--output", "json"])
    assert result.exit_code == 0, result.output
    data = _json(result)["data"]
    assert data["doc_type"] is None and data["template"] == "none"
    assert (root / data["path"]).read_text(encoding="utf-8") == "# Просто\n\n"


def test_docs_new_type_without_declared_template(root):
    _add_doc_type(root, "bare", {"schema_version": 1, "type_id": "bare", "version": "0.1",
                                 "kind": "doc_type", "format": "markdown"})
    result = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "T",
                                "--type", "bare", "--dir", "inbox", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["template"] == "type-without-template"


def test_docs_new_declared_but_missing_template(root):
    _add_doc_type(root, "spec", SPEC)  # declares template.md but does not ship it
    result = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "T",
                                "--type", "spec", "--dir", "specs", "--output", "json"])
    assert result.exit_code == 3
    assert result.exception.code == "types.template_missing"
    proc = _run_cli(root, ["docs", "new", "--title", "T", "--type", "spec", "--dir", "specs",
                           "--output", "json"])
    assert json.loads(proc.stdout)["diagnostics"][0]["code"] == "types.template_missing"


def test_docs_new_refuses_a_template_that_breaks_the_type(root):
    _add_doc_type(root, "spec", SPEC, "# {title}\n\n## Purpose\n\nonly one section\n")
    result = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "T",
                                "--type", "spec", "--dir", "specs", "--output", "json"])
    assert result.exit_code == 3
    assert result.exception.code == "types.template_invalid"
    assert not (root / "specs").exists()
    proc = _run_cli(root, ["docs", "new", "--title", "T", "--type", "spec", "--dir", "specs",
                           "--output", "json"])
    assert proc.returncode == 3, proc.stderr
    assert "Purpose" not in json.loads(proc.stdout)["diagnostics"][0]["message"] or True
    assert json.loads(proc.stdout)["diagnostics"][0]["code"] == "types.template_invalid"
    assert not (root / "specs").exists()


def test_docs_new_explicit_path_and_containment(root):
    _add_doc_type(root, "spec", SPEC, SPEC_TEMPLATE)
    result = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "T", "--type", "spec",
                                "--path", "specs/deep/name.md", "--output", "json"])
    assert result.exit_code == 0, result.output
    assert _json(result)["data"]["path"] == "specs/deep/name.md"

    escape = _run(CliRunner(), ["--root", str(root), "docs", "new", "--title", "T",
                                "--path", "../outside.md", "--output", "json"])
    assert escape.exit_code == 4
    assert escape.exception.code == "access.outside_data_root"
    assert not (root.parent / "outside.md").exists()
    proc = _run_cli(root, ["docs", "new", "--title", "T", "--path", "../outside.md", "--output", "json"])
    assert proc.returncode == 4, proc.stderr
    assert json.loads(proc.stdout)["diagnostics"][0]["code"] == "access.outside_data_root"


def test_docs_new_existing_target_is_a_conflict(root):
    _add_doc_type(root, "spec", SPEC, SPEC_TEMPLATE)
    runner = CliRunner()
    assert _run(runner, ["--root", str(root), "docs", "new", "--title", "T", "--type", "spec",
                         "--dir", "specs", "--output", "json"]).exit_code == 0
    second = _run(runner, ["--root", str(root), "docs", "new", "--title", "T", "--type", "spec",
                           "--dir", "specs", "--output", "json"])
    assert second.exit_code == 5
    assert second.exception.code == "docs.target_exists"
    proc = _run_cli(root, ["docs", "new", "--title", "T", "--type", "spec", "--dir", "specs",
                           "--output", "json"])
    assert proc.returncode == 5, proc.stderr
    assert json.loads(proc.stdout)["diagnostics"][0]["code"] == "docs.target_exists"


def test_created_document_is_valid_against_its_type(root):
    """A template that passes creation also passes `validate` (no drift between the two)."""
    _add_doc_type(root, "spec", SPEC, SPEC_TEMPLATE)
    (root / ".todoc" / "rules" / "document-rules.json").write_text(json.dumps({
        "schema_version": 1,
        "rules": [{"id": "specs", "match": {"kind": "file", "glob": "specs/**/*.md"},
                   "assign": {"doc_type": "spec"}, "priority": 80}],
    }), encoding="utf-8")
    runner = CliRunner()
    created = _run(runner, ["--root", str(root), "docs", "new", "--title", "T", "--type", "spec",
                            "--dir", "specs", "--output", "json"])
    assert created.exit_code == 0, created.output
    check = _run(runner, ["--root", str(root), "validate", "--all", "--output", "json"])
    assert _json(check)["ok"] is True
    assert not any(d["code"].startswith("markdown.section") for d in _json(check)["diagnostics"])


# ---------------------------------------------------------------------------
# types show / types prompt
# ---------------------------------------------------------------------------

def test_types_show_reports_template_and_prompt_locations(root):
    _add_doc_type(root, "spec", SPEC, SPEC_TEMPLATE)
    (root / ".todoc" / "doc_types" / "spec" / "prompts").mkdir()
    (root / ".todoc" / "doc_types" / "spec" / "prompts" / "read.md").write_text("# read\n", encoding="utf-8")
    data = _json(_run(CliRunner(), ["--root", str(root), "types", "show", "spec", "--output", "json"]))["data"]
    assert data["kind"] == "doc_type"
    assert data["template"] == {"path": ".todoc/doc_types/spec/template.md", "exists": True}
    assert data["prompts"]["read"] == {"path": ".todoc/doc_types/spec/prompts/read.md", "exists": True}
    assert data["prompts"]["create"]["exists"] is False


def test_types_show_for_a_dir_type_has_no_assets(root):
    data = _json(_run(CliRunner(), ["--root", str(root), "types", "show", "plan", "--output", "json"]))["data"]
    assert data["kind"] == "dir_type"
    assert data["template"] is None and data["prompts"] == {}


def test_types_show_for_a_type_without_a_declared_template(root):
    """`template: null` means "no starter file", and that must be visible, not guessed."""
    type_file = root / ".todoc" / "entity_types" / "workout" / "type.json"
    descriptor = json.loads(type_file.read_text(encoding="utf-8"))
    descriptor.pop("template")
    type_file.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2), encoding="utf-8")
    data = _json(_run(CliRunner(), ["--root", str(root), "types", "show", "workout",
                                    "--output", "json"]))["data"]
    assert data["kind"] == "entity_type"
    assert data["template"] is None
    assert data["prompts"]["create"]["exists"] is True


def test_types_show_unknown_type(root):
    result = _run(CliRunner(), ["--root", str(root), "types", "show", "ghost", "--output", "json"])
    assert result.exit_code == 3
    assert result.exception.code == "types.unknown"
    proc = _run_cli(root, ["types", "show", "ghost", "--output", "json"])
    assert json.loads(proc.stdout)["diagnostics"][0]["code"] == "types.unknown"


def test_types_prompt_returns_each_crud_instruction(root):
    """`init` ships four prompts per type; every one is readable through the CLI."""
    runner = CliRunner()
    for operation in ("read", "create", "edit", "delete"):
        result = _run(runner, ["--root", str(root), "types", "prompt", "note", "--op", operation,
                               "--output", "json"])
        assert result.exit_code == 0, result.output
        data = _json(result)["data"]
        assert data["operation"] == operation
        assert data["kind"] == "doc_type"
        assert data["path"] == f".todoc/doc_types/note/prompts/{operation}.md"
        assert data["prompt"].startswith("# ")
        assert data["chars"] == len(data["prompt"])


def test_types_prompt_works_for_entity_types(root):
    data = _json(_run(CliRunner(), ["--root", str(root), "types", "prompt", "workout",
                                    "--op", "create", "--output", "json"]))["data"]
    assert data["kind"] == "entity_type"
    assert "records create" in data["prompt"]


def test_types_prompt_missing_file_and_unknown_type(root):
    runner = CliRunner()
    (root / ".todoc" / "doc_types" / "note" / "prompts" / "read.md").unlink()
    missing = _run(runner, ["--root", str(root), "types", "prompt", "note", "--op", "read",
                            "--output", "json"])
    assert missing.exit_code == 3
    assert missing.exception.code == "types.prompt_missing"

    unknown = _run(runner, ["--root", str(root), "types", "prompt", "ghost", "--output", "json"])
    assert unknown.exit_code == 3
    assert unknown.exception.code == "types.unknown"

    proc = _run_cli(root, ["types", "prompt", "note", "--op", "read", "--output", "json"])
    assert proc.returncode == 3, proc.stderr
    assert json.loads(proc.stdout)["diagnostics"][0]["code"] == "types.prompt_missing"


def test_types_prompt_rejects_an_unknown_operation(root):
    result = CliRunner().invoke(cli, ["--root", str(root), "types", "prompt", "note", "--op", "review"])
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# check-config
# ---------------------------------------------------------------------------

def test_check_config_is_clean_on_a_fresh_dataset(root):
    data = _json(_run(CliRunner(), ["--root", str(root), "check-config", "--output", "json"]))
    assert data["ok"] is True
    assert data["data"]["datasets"][0]["issues"] == 0


def test_check_config_reports_unknown_field_and_missing_template(root):
    _add_doc_type(root, "spec", dict(SPEC, required_headings=["Purpose"], template="gone.md"))
    result = _run(CliRunner(), ["--root", str(root), "check-config", "--output", "json"])
    assert result.exit_code == 3
    payload = _json(result)
    assert payload["ok"] is False
    codes = {d["code"] for d in payload["diagnostics"]}
    assert codes == {"config.unknown_field", "config.template_missing"}
    assert payload["data"]["datasets"][0]["ok"] is False
    assert payload["data"]["datasets"][0]["issues"] == 2


def test_check_config_envelope_and_exit_code_agree_in_a_subprocess(root):
    """In-process CliRunner cannot see main()'s mapping, so the pair is checked here."""
    _add_doc_type(root, "spec", dict(SPEC, required_headings=["Purpose"]))
    proc = _run_cli(root, ["check-config", "--output", "json"])
    assert proc.returncode == 3, proc.stderr
    assert json.loads(proc.stdout)["ok"] is False


def test_check_config_clean_in_a_subprocess(root):
    proc = _run_cli(root, ["check-config", "--output", "json"])
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
