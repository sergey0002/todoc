"""Failure contracts for selectors, review-first actions, and ambiguous sources."""

import json
import os

import pytest
from click.testing import CliRunner

from todoc.cli import cli
from todoc.config import init_dataset
from todoc.service import DatasetContext


def call(root, *args):
    return CliRunner().invoke(cli, ["--root", str(root), *args])


def diagnostic_code(result):
    if result.output:
        return json.loads(result.output)["diagnostics"][0]["code"]
    return getattr(result.exception, "code", None)


@pytest.mark.parametrize(("args", "code"), [
    (("docs", "search", "--query", " "), "usage.error"),
    (("records", "list", "--relation", "missing-equals"), "filter.invalid"),
    (("records", "query"), "usage.error"),
    (("docs", "status", "--id", "doc:notes/design.md", "--apply"), "usage.error"),
    (("records", "status", "--id", "workout:2026-11-24-sergei-01", "--apply"), "usage.error"),
    (("docs", "flow", "render", "--id", "flow:absent", "--apply"), "usage.error"),
    (("interop", "export", "--kind", "rasa", "--apply"), "usage.error"),
    (("types", "guide", "--apply"), "usage.error"),
    (("stale", "--apply"), "usage.error"),
    (("doctor", "--check", "unsupported"), "usage.error"),
    (("change", "archive", "change:absent"), "change.not_found"),
    (("context", "--change", "change:absent"), "change.not_found"),
    (("history", "export", "--to", ".todoc/history/backup"), "access.outside_data_root"),
    (("docs", "new", "--title", " ", "--path", "empty.json"), "docs.empty_title"),
    (("records", "read", "--id", "workout:2026-11-24-sergei-01", "--view", "full",
      "--record-view", "summary"), "view.conflict"),
    (("docs", "read", "--id", "doc:notes/design.md", "--pointer", "/title"), "docs.invalid_selector"),
    (("docs", "read", "--id", "doc:data/runs.csv", "--budget", "7"), "docs.budget_not_applicable"),
    (("docs", "read", "--id", "doc:data/runs.csv", "--columns", "absent"), "docs.invalid_selector"),
    (("docs", "read", "--id", "doc:data/runs.csv", "--where", "invalid"), "docs.invalid_selector"),
])
def test_unsupported_modes_and_selectors_refuse_without_writing(root, sample_md, sample_csv, sample_record,
                                                                 args, code):
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    result = call(root, *args)
    assert diagnostic_code(result) == code, (args, result.output, result.exception)
    assert {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize(("args", "code"), [
    (("docs", "search", "--query", "design"), "docs.multiple_roots"),
    (("docs", "read", "--id", "doc:notes/design.md"), "docs.multiple_roots"),
    (("log",), "history.multiple_roots"),
    (("relations", "graph", "--from", "note:x"), "relations.multiple_roots"),
    (("relations", "tree", "--from", "note:x"), "relations.multiple_roots"),
    (("records", "list"), "records.multiple_roots"),
    (("docs", "edit", "--id", "doc:notes/design.md", "--patch-file", "patch.json"), "docs.multiple_roots"),
    (("records", "edit", "--id", "workout:2026-11-24-sergei-01", "--patch-file", "patch.json"),
     "records.multiple_roots"),
    (("types", "metadata"), "types.multiple_roots"),
])
def test_selectors_reject_ambiguous_dataset_scope(root, tmp_path, args, code):
    other = tmp_path / "second"
    init_dataset(other)
    result = CliRunner().invoke(cli, ["--root", str(root), "--root", str(other), *args])
    assert diagnostic_code(result) == code, (args, result.output, result.exception)


def test_separators_only_todoc_root_is_missing(monkeypatch):
    monkeypatch.setenv("TODOC_ROOT", os.pathsep)
    result = CliRunner().invoke(cli, ["docs", "list"])
    assert diagnostic_code(result) == "usage.missing_root"
    assert result.exit_code == 2


def test_duplicate_record_and_document_identity_are_rejected(root, sample_md, sample_record):
    header = "---\nid: doc:duplicate\ntitle: Duplicate\n---\n# Test\n"
    sample_md.write_text(header, encoding="utf-8")
    sample_md.with_name("duplicate.md").write_text(header, encoding="utf-8")
    sample_record.with_name("duplicate.json").write_bytes(sample_record.read_bytes())
    doc = call(root, "docs", "read", "--id", "doc:duplicate")
    record = call(root, "records", "read", "--id", "workout:2026-11-24-sergei-01")
    assert doc.exception.code == "docs.ambiguous_id"
    assert record.exception.code == "records.ambiguous_id"


def test_init_existing_and_stale_plans_never_overwrite(root, tmp_path):
    assert call(root, "init", "--root", str(root), "--apply").exception.code == "config.already_initialized"
    path = tmp_path / "future-dataset"
    refused = call(root, "init", "--root", str(path), "--apply", "--if-plan-hash", "stale")
    assert refused.exception.code == "write.hash_mismatch" and not path.exists()
    schema = root / ".todoc/document-metadata.schema.json"
    schema.write_text("{}", encoding="utf-8")
    refused = call(root, "init", "--root", str(root), "--document-metadata")
    assert refused.exception.code == "metadata.schema_exists"
    assert schema.read_text(encoding="utf-8") == "{}"


def test_review_modes_and_stale_tag_do_not_change_existing_journal(root, sample_md):
    ctx = DatasetContext(root)
    ctx.history_recorder().record("notes/design.md", b"old", b"current", "doc.edit")
    store = ctx.history_store
    events = store.read_events(strict=True)
    revision = events[0]["rev"]
    for args in (("revert", revision, "--path", "notes/design.md"),
                 ("tag", "demo"), ("history", "adopt"), ("history", "export", "--to", "backup")):
        result = call(root, *args, "--apply", "--preview")
        assert result.exception.code == "usage.error"
    denied = call(root, "tag", "demo", "--apply", "--if-plan-hash", "stale")
    assert denied.exception.code == "write.hash_mismatch"
    assert store.read_events(strict=True) == events
    assert store.read_refs()["tags"] == {}



@pytest.mark.parametrize("kind", ["docs", "records"])
def test_status_preview_binds_candidate_to_source_without_writing(root, sample_md, sample_record, kind):
    if kind == "docs":
        source = sample_md
        source.write_text("---\ntitle: Example\nstatus: open\n---\n# Content\n", encoding="utf-8")
        identity = "doc:notes/design.md"
    else:
        source = sample_record
        identity = "workout:2026-11-24-sergei-01"
    args = [kind, "status", "--id", identity, "--set", "closed"]
    before = source.read_bytes()
    preview = call(root, *args)
    assert preview.exit_code == 0, preview.exception
    plan = json.loads(preview.output)["data"]["result"]
    assert not plan["applied"] and source.read_bytes() == before
    refused = call(root, *args, "--apply", "--if-plan-hash", "stale")
    assert diagnostic_code(refused) == "write.hash_mismatch"
    assert source.read_bytes() == before


def test_change_archive_and_export_refuse_stale_or_existing_destinations(root):
    opened = call(root, "change", "open", "--title", "Review", "--apply")
    assert opened.exit_code == 0, opened.exception
    denied = call(root, "change", "archive", "change:review", "--apply", "--if-plan-hash", "stale")
    assert diagnostic_code(denied) == "write.hash_mismatch"
    assert (root / "changes/review/change.json").is_file()
    (root / "backup").mkdir()
    denied = call(root, "history", "export", "--to", "backup")
    assert diagnostic_code(denied) == "write.target_exists"


def test_record_create_refuses_unreviewed_plan_without_a_target(root, sample_record, tmp_path):
    data = json.loads(sample_record.read_text())
    data["record_id"] = "workout:new-sample"
    input_file = tmp_path / "draft.json"
    input_file.write_text(json.dumps(data), encoding="utf-8")
    args = ["records", "create", "--type", "workout", "--input-file", str(input_file)]
    assert diagnostic_code(call(root, *args, "--apply", "--preview")) == "usage.error"
    preview = call(root, *args)
    assert preview.exit_code == 0, preview.exception
    rel = json.loads(preview.output)["data"]["result"]["plan"]["target_path"]
    assert not (root / rel).exists()
    assert diagnostic_code(call(root, *args, "--apply", "--if-plan-hash", "stale")) == "write.hash_mismatch"
    assert not (root / rel).exists()


@pytest.mark.parametrize(("body", "code"), [
    ('{"id":"doc:overridden"}', "metadata.protected"),
    ('{"tags":"invalid"}', "markdown.tags_invalid"),
])
def test_new_document_rejects_protected_and_invalid_metadata(root, tmp_path, body, code):
    attributes = tmp_path / "attributes.json"
    attributes.write_text(body, encoding="utf-8")
    result = call(root, "docs", "new", "--title", "Review", "--path", "review.md", "--type", "note",
                  "--attributes-file", str(attributes))
    assert diagnostic_code(result) == code, (result.exception, result.output)
    assert not (root / "review.md").exists()


def test_json_creation_uses_content_of_explicit_template(root):
    template = root / "body.json"
    template.write_text('{"body_marker":42}', encoding="utf-8")
    args = ["docs", "new", "--title", "Review", "--path", "review.json", "--template", "body.json"]
    result = call(root, *args)
    assert result.exit_code == 0, result.exception
    plan = json.loads(result.output)["data"]["result"]["plan"]
    assert json.loads(plan["new_content"])["body"] == {"body_marker": 42}
    template.write_text("{", encoding="utf-8")
    assert diagnostic_code(call(root, *args)) == "types.template_invalid"
    assert not (root / "review.json").exists()


@pytest.mark.parametrize(("kind", "args"), [
    ("document", ("docs", "edit", "--id", "doc:notes/design.md")),
    ("record", ("records", "edit", "--id", "workout:2026-11-24-sergei-01")),
])
def test_structured_metadata_patch_checks_mode_and_hash(root, sample_md, sample_record, tmp_path, kind, args):
    file = tmp_path / "patch.json"
    file.write_text('{"metadata":[{"field":"extra","op":"set","value":"value"}]}', encoding="utf-8")
    cli_args = [*args, "--patch-file", str(file)]
    original = sample_md.read_bytes() if kind == "document" else sample_record.read_bytes()
    assert diagnostic_code(call(root, *cli_args, "--apply", "--preview")) == "edit.invalid_patch"
    result = call(root, *cli_args, "--apply")
    assert diagnostic_code(result) == "usage.error"
    assert (sample_md if kind == "document" else sample_record).read_bytes() == original



def test_skill_import_manifest_binds_nested_file_changes(root, tmp_path):
    source = tmp_path / "candidate"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: candidate\ndescription: A candidate skill\n---\n# Candidate\n", encoding="utf-8")
    path = scripts / "sample.txt"
    path.write_text("before", encoding="utf-8")
    args = ["skills", "import", "--src", str(source), "--into", "process"]
    result = call(root, *args)
    assert result.exit_code == 0, result.exception
    plan = json.loads(result.output)["data"]["result"]
    assert {file["path"] for file in plan["manifest"][0]["files"]} == {"SKILL.md", "scripts/sample.txt"}
    assert not (root / "skills/process/candidate").exists()
    path.write_text("after", encoding="utf-8")
    denied = call(root, *args, "--apply", "--if-plan-hash", plan["plan_hash"])
    assert diagnostic_code(denied) == "write.hash_mismatch"
    assert not (root / "skills/process/candidate").exists()


def test_init_refuses_existing_symlinked_control_directory(tmp_path):
    root = tmp_path / "candidate"
    root.mkdir()
    outside = tmp_path / "external"
    outside.mkdir()
    control = root / ".todoc"
    try:
        control.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    assert diagnostic_code(call(root, "init", "--root", str(root), "--apply")) == "access.outside_data_root"
    assert not list(outside.iterdir())


def test_unreadable_scan_is_returned_as_an_incomplete_result(root, monkeypatch):
    def fail(self, *, strict=False):
        raise OSError("injected bad filesystem")

    monkeypatch.setattr(DatasetContext, "scan", fail)
    result = call(root, "scan")
    assert result.exit_code != 0
    assert getattr(result.exception, "exit_code", 0) == 6


def test_missing_skill_path_returns_discovery_without_scanning(root):
    result = call(root, "skills", "read")
    assert result.exit_code == 0
    response = json.loads(result.output)
    assert response["data"]["executed"] is False
    assert response["data"]["result"]["input"] == "Pass --path."



def test_skill_missing_and_invalid_utf8_have_distinct_diagnostics(root):
    absent = call(root, "skills", "read", "--path", "absent")
    assert diagnostic_code(absent) == "skills.not_found"
    path = root / "skills/broken/SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff")
    unreadable = call(root, "skills", "read", "--path", "broken")
    assert diagnostic_code(unreadable) == "skills.missing_front_matter"


def test_skill_truncation_action_preserves_line_range(root):
    path = root / "skills/example/SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nname: example\ndescription: Example\n---\nSome body.\n", encoding="utf-8")
    result = call(root, "skills", "read", "--path", "example", "--line-range", "1-3", "--budget", "2")
    assert result.exit_code == 0, result.exception
    envelope = json.loads(result.output)
    assert envelope["data"]["result"]["truncated"]
    assert envelope["next_actions"][0]["argv"][-2:] == ["--line-range", "1-3"]


def test_skill_line_range_past_end_is_rejected(root):
    path = root / "skills/example/SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nname: example\ndescription: Example\n---\nSome body.\n", encoding="utf-8")
    result = call(root, "skills", "read", "--path", "example", "--line-range", "99-100")
    assert diagnostic_code(result) == "usage.invalid_line_range"


@pytest.mark.parametrize("fault", ["redirect", "unreadable", "changed-metadata"])
def test_skill_read_refuses_changes_between_discovery_and_source_read(root, tmp_path, monkeypatch, fault):
    import todoc.cli as entry

    target = root / "skills/example/SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("---\nname: example\ndescription: Example\n---\nBody\n", encoding="utf-8")
    outside = tmp_path / "other.md"
    outside.write_bytes(target.read_bytes())
    scan = entry.scan_skills
    file_hash = entry.file_hash

    def after_scan(path):
        result = scan(path)
        if fault == "redirect":
            target.unlink()
            try:
                target.symlink_to(outside)
            except OSError:
                pytest.skip("symlinks unavailable")
        elif fault == "changed-metadata":
            target.write_text("---\nname: changed\ndescription: Example\n---\nBody\n", encoding="utf-8")
        return result

    def hash_path(path):
        if fault == "unreadable" and path == target:
            raise PermissionError("lost access")
        return file_hash(path)

    monkeypatch.setattr(entry, "scan_skills", after_scan)
    monkeypatch.setattr(entry, "file_hash", hash_path)
    error = call(root, "skills", "read", "--path", "example")
    expected = {"redirect": "access.outside_data_root", "unreadable": "file.unreadable",
                "changed-metadata": "read.changed"}
    assert diagnostic_code(error) == expected[fault]


@pytest.mark.parametrize("fault", ["planned-symlink", "late-symlink", "late-edit", "late-create"])
def test_skill_attach_never_overwrites_concurrent_destination(root, tmp_path, monkeypatch, fault):
    import todoc.cli as entry

    location = tmp_path / "agent"
    dest = location / "todoc/SKILL.md"
    dest.parent.mkdir(parents=True)
    outside = tmp_path / "other.md"
    outside.write_text("untouched", encoding="utf-8")
    if fault == "late-edit":
        dest.write_text("before", encoding="utf-8")

    def redirect():
        try:
            dest.symlink_to(outside)
        except OSError:
            pytest.skip("symlinks unavailable")

    if fault == "planned-symlink":
        redirect()
    original_key = entry.selection_key
    original_write = entry.atomic_write

    def manifest_key(selection):
        key = original_key(selection)
        if fault == "late-symlink":
            redirect()
        elif fault == "late-edit":
            dest.write_text("concurrent", encoding="utf-8")
        return key

    def publish(path, content, **kwargs):
        if path == dest and fault == "late-create":
            path.write_text("concurrent", encoding="utf-8")
        return original_write(path, content, **kwargs)

    monkeypatch.setattr(entry, "selection_key", manifest_key)
    monkeypatch.setattr(entry, "atomic_write", publish)
    result = call(root, "skills", "attach", "--to", str(location), "--force", "--apply")
    expected = {"planned-symlink": "access.outside_data_root", "late-symlink": "access.outside_data_root",
                "late-edit": "write.hash_mismatch", "late-create": "attach.exists"}
    assert diagnostic_code(result) == expected[fault]
    assert outside.read_text(encoding="utf-8") == "untouched"


@pytest.mark.parametrize("fault", ["destination-symlink", "source-symlink", "special-file", "concurrent"])
def test_skill_import_rejects_unsafe_or_changed_paths(root, tmp_path, monkeypatch, fault):
    import os
    import shutil

    source = tmp_path / "candidate"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: candidate\ndescription: Example\n---\n", encoding="utf-8")
    destination = root / "skills/process/candidate"
    if fault == "special-file":
        if not hasattr(os, "mkfifo"):
            pytest.skip("FIFO unavailable")
        os.mkfifo(source / "pipe")
    elif fault == "concurrent":
        def collide(*args, **kw):
            raise FileExistsError("destination already created")
        monkeypatch.setattr(shutil, "copytree", collide)
    else:
        try:
            if fault == "destination-symlink":
                destination.parent.mkdir(parents=True)
                destination.symlink_to(tmp_path, target_is_directory=True)
            else:
                (source / "alias").symlink_to(source / "SKILL.md")
        except OSError:
            pytest.skip("symlinks unavailable")
    result = call(root, "skills", "import", "--src", str(source), "--into", "process", "--apply")
    expected = {"destination-symlink": "access.outside_data_root", "source-symlink": "access.outside_data_root",
                "special-file": "skills.unsupported_source", "concurrent": "skills.path_exists"}
    assert diagnostic_code(result) == expected[fault]


def test_skill_dispatcher_preview_does_not_create_destination(root, tmp_path):
    dest = tmp_path / "dispatcher"
    response = call(root, "skills", "attach", "--to", str(dest))
    assert response.exit_code == 0, response.exception
    assert json.loads(response.output)["data"]["result"]["applied"] is False
    assert not dest.exists()


@pytest.mark.parametrize(("fault", "code"), [
    ("absent", "history.source_unreadable"),
    ("removed", "history.source_unreadable"),
    ("modified", "history.source_changed"),
])
def test_section_log_refuses_to_page_a_changed_source(root, monkeypatch, fault, code):
    (root / "notes").mkdir(exist_ok=True)
    import todoc.cli as entry

    rel = "notes/section-log.md"
    source = root / rel
    if fault != "absent":
        source.write_text("# Plan\n\nBefore.\n", encoding="utf-8")
    history_log = entry.history_log

    def read_history(*args, **kwargs):
        output = history_log(*args, **kwargs)
        if fault == "removed":
            source.unlink()
        else:
            source.write_text("# Plan\n\nAfter.\n", encoding="utf-8")
        return output

    monkeypatch.setattr(entry, "history_log", read_history)
    response = call(root, "log", "--path", rel, "--section", "Plan")
    assert diagnostic_code(response) == code
    assert json.loads(response.output)["data"]["meta"]["complete"] is False


@pytest.mark.parametrize(("args", "code"), [
    (("docs", "search", "--query", "design"), "file.unreadable"),
    (("records", "list"), "file.unreadable"),
    (("types", "metadata"), "file.unreadable"),
    (("history", "adopt", "--apply"), "history.source_unreadable"),
])
def test_collection_and_adoption_surface_unreadable_sources(root, args, code):
    (root / "notes").mkdir(exist_ok=True)
    (root / "notes" / "bad-encoding.md").write_bytes(b"\xff")
    response = call(root, *args)
    assert diagnostic_code(response) == code
    assert response.exit_code
    assert not (root / ".todoc/history/journal.jsonl").exists()


@pytest.mark.parametrize("args", [("docs", "read"), ("docs", "suggest")])
def test_incomplete_selection_returns_command_discovery(root, args):
    response = call(root, *args)
    assert response.exit_code == 0
    assert json.loads(response.output)["data"]["executed"] is False


def test_folder_suggestion_reports_a_bad_folder_config(root):
    (root / "notes").mkdir(exist_ok=True)
    (root / "notes" / ".config.json").write_text("{", encoding="utf-8")
    response = call(root, "docs", "suggest", "--query", "design")
    assert response.exit_code
    assert json.loads(response.output)["data"]["meta"]["complete"] is False


def test_metadata_preview_reports_violations_on_managed_documents(root):
    (root / "notes").mkdir(exist_ok=True)
    (root / "notes" / "managed.md").write_text(
        "---\ndoc_type: note\ntitle: Managed\n---\n# Managed\n", encoding="utf-8"
    )
    response = call(root, "types", "metadata")
    assert response.exit_code == 0, response.exception
    result = json.loads(response.output)["data"]["result"]
    managed = next(item for item in result["items"] if item["path"] == "notes/managed.md")
    assert any("created" in issue["message"] for issue in managed["violations"])


@pytest.mark.parametrize(("option", "expected"), [
    ("--if-hash", "write.hash_mismatch"),
    ("--if-plan-hash", "write.hash_mismatch"),
    (None, "fix.cannot_apply"),
])
def test_fix_refuses_stale_or_ambiguous_link_evidence(root, option, expected):
    (root / "notes").mkdir(exist_ok=True)
    (root / "notes" / "runbook.md").write_text("# Runbook\n", encoding="utf-8")
    link = "[runbook](runbok.md)"
    original = f"# Broken\n\n{link} "
    if option is None:
        original += link
    source = root / "notes" / "broken.md"
    source.write_text(original, encoding="utf-8")
    validation = json.loads(call(root, "validate", "--all").output)
    issue = next(item for item in validation["diagnostics"] if item["code"] == "markdown.link.target_missing")
    options = [option, "stale"] if option else []
    response = call(root, "fix", "--diagnostic", issue["id"], "--apply", *options)
    assert diagnostic_code(response) == expected
    assert source.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("args", [
    ("docs", "search", "--query", "design"),
    ("docs", "tree"),
    ("relations", "graph", "--from", "doc:notes/design.md"),
])
def test_unavailable_view_returns_a_fallback_diagnostic(root, args):
    response = call(root, *args, "--view", "unavailable")
    assert response.exit_code == 0, response.exception
    envelope = json.loads(response.output)
    assert any(issue["code"] == "view.fallback" for issue in envelope["diagnostics"])
    assert envelope["data"]["meta"]["requested_view"] == "unavailable"
    assert envelope["data"]["meta"]["actual_view"] != "unavailable"


def test_main_reports_errors_raised_before_command_context(monkeypatch, capsys):
    import todoc.cli as entry
    from todoc.errors import ValidationError

    def fail(*args, **kwargs):
        raise ValidationError("Unable to load defaults", "config.invalid")

    monkeypatch.setattr(entry, "cli", fail)
    with pytest.raises(SystemExit) as caught:
        entry.main()
    assert caught.value.code != 0
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "config.invalid"


def test_docs_new_does_not_replace_a_dangling_alias(root):
    alias = root / "alias.md"
    try:
        alias.symlink_to(root / "missing.md")
    except OSError:
        pytest.skip("symlinks unavailable")
    response = call(root, "docs", "new", "--title", "Example", "--path", "alias.md", "--apply")
    assert diagnostic_code(response) == "docs.target_exists"
    assert alias.is_symlink() and not (root / "missing.md").exists()


@pytest.mark.parametrize(("attributes", "error"), [
    ({"tags": ["useful"]}, None),
    ({"priority": 5}, "metadata.invalid_patch"),
    ({"tags": "invalid"}, "markdown.tags_invalid"),
])
def test_docs_new_checks_attributes_without_common_schema(root, tmp_path, attributes, error):
    attrs = tmp_path / "attributes.json"
    attrs.write_text(json.dumps(attributes), encoding="utf-8")
    preview = call(root, "docs", "new", "--title", "Example", "--path", "example.md",
                   "--attributes-file", str(attrs))
    if error:
        assert diagnostic_code(preview) == error
    else:
        assert preview.exit_code == 0, preview.exception
        assert json.loads(preview.output)["data"]["result"]["attributes"]["tags"] == ["useful"]
    assert not (root / "example.md").exists()


def test_docs_search_omits_ambiguous_follow_up_and_refuses_out_of_range_cursor(root):
    for name in ("a.md", "b.md"):
        (root / name).write_text("---\nid: doc:duplicate\n---\n# Design\n", encoding="utf-8")
    args = ("docs", "search", "--query", "design", "--limit", "1")
    first = json.loads(call(root, *args).output)
    assert not first.get("next_actions")
    cursor = first["data"]["meta"]["next_cursor"]
    assert cursor
    fingerprint, _, _offset = cursor.rpartition(":")
    second = call(root, *args, "--cursor", f"{fingerprint}:99")
    assert diagnostic_code(second) == "cursor.invalid"


def test_preview_keeps_guide_and_change_in_place(root):
    guide = call(root, "types", "guide", "--out", "guide.md")
    assert guide.exit_code == 0, guide.exception
    assert json.loads(guide.output)["data"]["result"]["applied"] is False
    assert not (root / "guide.md").exists()
    created = call(root, "change", "open", "--title", "Keep this change", "--apply")
    assert created.exit_code == 0, created.exception
    item = json.loads(created.output)["data"]["result"]
    archived = call(root, "change", "archive", item["change_id"])
    assert archived.exit_code == 0, archived.exception
    assert json.loads(archived.output)["data"]["result"]["applied"] is False
    assert (root / item["path"]).is_file()


def test_main_reports_a_malformed_attribute_option(root, monkeypatch, capsys):
    import sys
    import todoc.cli as entry

    monkeypatch.setattr(sys, "argv", ["todoc", "--root", str(root), "docs", "list", "--attr-title"])
    with pytest.raises(SystemExit) as caught:
        entry.main()
    assert caught.value.code != 0
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "usage.error"


@pytest.mark.parametrize(("suffix", "text", "error"), [
    ("json", "{", "docs.invalid_json"),
    ("csv", "id,id\n1,2\n", "docs.invalid_csv"),
])
def test_read_cannot_project_invalid_documents(root, suffix, text, error):
    (root / f"bad.{suffix}").write_text(text, encoding="utf-8")
    response = call(root, "docs", "read", "--id", f"doc:bad.{suffix}")
    assert diagnostic_code(response) == error


def test_tree_refuses_an_incomplete_scan(root):
    (root / "bad.md").write_bytes(b"\xff")
    response = call(root, "docs", "tree")
    assert diagnostic_code(response) == "file.unreadable"
    assert json.loads(response.output)["data"]["meta"]["complete"] is False


def test_docs_links_refuses_unknown_projection(root):
    response = call(root, "docs", "links", "--fields", "unknown")
    assert diagnostic_code(response) == "fields.unknown"


def test_docs_edit_checks_legacy_metadata(root, tmp_path):
    source = root / "example.md"
    original = "---\ntitle: Example\n---\n# Example\n"
    source.write_text(original, encoding="utf-8")
    patch = tmp_path / "edit.json"
    patch.write_text('{"metadata":[{"op":"set","field":"tags","value":"invalid"}]}', encoding="utf-8")
    args = ("docs", "edit", "--id", "doc:example.md", "--patch-file", str(patch))
    assert diagnostic_code(call(root, *args)) == "markdown.tags_invalid"
    assert source.read_text(encoding="utf-8") == original


def test_docs_metadata_edit_refuses_duplicate_identity(root, tmp_path):
    for name in ("a.md", "b.md"):
        (root / name).write_text("---\nid: doc:duplicate\n---\n# Existing\n", encoding="utf-8")
    patch = tmp_path / "edit.json"
    patch.write_text('{"metadata":[{"op":"set","field":"title","value":"Example"}]}', encoding="utf-8")
    response = call(root, "docs", "edit", "--id", "doc:duplicate", "--patch-file", str(patch))
    assert diagnostic_code(response) == "docs.ambiguous_id"


def test_records_edit_requires_an_existing_record_and_honors_its_schema(root, sample_record, tmp_path):
    base = root / ".todoc/entity_types/workout"
    base.mkdir(exist_ok=True, parents=True)
    descriptor = {"schema_version": 1, "kind": "entity_type", "type_id": "workout", "version": "1.0",
                  "description": "Workout", "format": "json"}
    (base / "type.json").write_text(json.dumps(descriptor), encoding="utf-8")
    schema = {"type": "object", "properties": {"date": {"type": "string"}}}
    (base / "schema.json").write_text(json.dumps(schema), encoding="utf-8")
    patch = tmp_path / "edit.json"
    patch.write_text('{"metadata":[{"op":"set","field":"date","value":42}]}', encoding="utf-8")
    args = ("records", "edit", "--patch-file", str(patch), "--id")
    absent = call(root, *args, "workout:absent")
    assert diagnostic_code(absent) == "records.not_found"
    malformed = call(root, *args, "workout:2026-11-24-sergei-01")
    assert diagnostic_code(malformed) == "document.schema_violation"


def test_invalid_record_comparisons_are_diagnosed(root, sample_record, tmp_path):
    file = tmp_path / "query.json"
    file.write_text('{"filters":{"date":{"$gte":42}}}', encoding="utf-8")
    query = call(root, "records", "query", "--query-file", str(file))
    assert diagnostic_code(query) == "query.invalid_file"
    record = json.loads(sample_record.read_text(encoding="utf-8"))
    record["date"] = 42
    sample_record.write_text(json.dumps(record), encoding="utf-8")
    dates = call(root, "records", "list", "--since", "2026-01-01")
    assert diagnostic_code(dates) == "filter.invalid"


@pytest.mark.parametrize("spec", [
    {"schema_version": 2},
    {"unknown": True},
    {"name": 1},
    {"entity_type": ""},
    {"filters": []},
    {"filters": {"": 1}},
    {"filters": {"date": {}}},
    {"filters": {"date": {"$regex": "x"}}},
    {"filters": {"date": {"$in": "x"}}},
    {"filters": {"date": {"$gte": [1]}}},
    {"filters": {"tags": ["a"]}},
    {"filters": {"date": {"$gte": 1, "$in": [1]}}},
    {"limit": 0},
])
def test_invalid_query_spec_is_rejected_before_index_read(root, tmp_path, monkeypatch, spec):
    file = tmp_path / "query.json"
    file.write_text(json.dumps(spec), encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("index must not be read for an invalid spec")

    monkeypatch.setattr(DatasetContext, "read_index", forbidden)
    result = call(root, "records", "query", "--query-file", str(file))
    assert diagnostic_code(result) == "query.invalid_file", (spec, result.output, result.exception)


@pytest.mark.parametrize("filters", [
    {"date": {"$in": ["2026-11-24"]}},
    {"date": "2026-11-24"},
    {"date": {"$gte": "2026-01-01", "$lte": "2026-12-31"}},
])
def test_valid_query_spec_filters_are_accepted(root, tmp_path, filters):
    file = tmp_path / "query.json"
    file.write_text(json.dumps({"entity_type": "workout", "filters": filters}), encoding="utf-8")
    result = call(root, "records", "query", "--query-file", str(file))
    assert result.exit_code == 0, (result.output, result.exception)
    assert json.loads(result.output)["ok"] is True


@pytest.mark.parametrize(("args", "code"), [
    (("records", "list", "--type", "adr"), "query.namespace_mismatch"),
    (("records", "list", "--type", "ghost"), "query.unknown_type"),
])
def test_records_type_namespace_is_checked_before_index(root, monkeypatch, args, code):
    def forbidden(*args, **kwargs):
        raise AssertionError("index must not be read")

    monkeypatch.setattr(DatasetContext, "read_index", forbidden)
    result = call(root, *args)
    assert diagnostic_code(result) == code, (args, result.output, result.exception)


def test_query_spec_namespace_is_checked_before_index(root, tmp_path, monkeypatch):
    file = tmp_path / "query.json"
    file.write_text(json.dumps({"entity_type": "adr"}), encoding="utf-8")

    def forbidden(*args, **kwargs):
        raise AssertionError("index must not be read")

    monkeypatch.setattr(DatasetContext, "read_index", forbidden)
    result = call(root, "records", "query", "--query-file", str(file))
    assert diagnostic_code(result) == "query.namespace_mismatch"


def test_known_record_type_without_records_is_an_empty_success(root):
    result = call(root, "records", "list", "--type", "link")
    assert result.exit_code == 0, result.exception
    envelope = json.loads(result.output)
    assert envelope["ok"] and envelope["data"]["result"]["items"] == []
    assert envelope["data"]["meta"]["total"] == 0


def test_relations_tree_refuses_matching_cursor_beyond_selection(root, sample_md):
    from todoc.application.paging import selection_key

    dataset = DatasetContext(root)
    payload = dataset.read_index()
    start = "doc:notes/design.md"
    key = selection_key([2, "relations tree", dataset.dataset_id, payload["corpus_digest"], start, None, 1])
    response = call(root, "relations", "tree", "--from", start, "--cursor", f"{key}:99")
    assert diagnostic_code(response) == "cursor.invalid"


def test_type_catalog_limits_rows_to_requested_kind(root):
    response = call(root, "types", "list", "--kind", "doc_type")
    assert response.exit_code == 0
    data = json.loads(response.output)["data"]
    assert data["meta"]["scope"]["kind"] == "doc_type"
    assert all(item["kind"] == "doc_type" for item in data["result"]["items"])


def test_types_metadata_ignores_unmanaged_bare_document(root):
    (root / "legacy.md").write_text("# Legacy note\n", encoding="utf-8")
    response = call(root, "types", "metadata")
    assert response.exit_code == 0
    assert json.loads(response.output)["data"]["result"]["inspected"] == 0


@pytest.mark.parametrize(("arguments", "message"), [
    (["--attr-!invalid=yes"], "Invalid attribute name"),
    (["--", "--attr-title=hello"], "unexpected extra argument"),
])
def test_attribute_options_respect_valid_names_and_option_delimiter(root, monkeypatch, capsys, arguments, message):
    import sys
    import todoc.cli as entry

    monkeypatch.setattr(sys, "argv", ["todoc", "--root", str(root), "docs", "list", *arguments])
    with pytest.raises(SystemExit) as caught:
        entry.main()
    assert caught.value.code != 0
    error = json.loads(capsys.readouterr().out)["diagnostics"][0]
    assert error["code"] == "usage.error" and message in error["message"]
