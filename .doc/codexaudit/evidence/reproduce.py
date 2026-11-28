"""Offline audit probes. Run from repository root: PYTHONPATH=src python3 <this file>."""
import json
import tempfile
import click
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from todoc.cli import cli
from todoc.application.registry import RegistryStore
from todoc.application.write import apply_write_plan
from todoc.adapters.filesystem.scanner import atomic_write
from todoc.domain.models import WritePlan


def invoke(root, *args):
    result = CliRunner().invoke(cli, ["--root", str(root), *args])
    try:
        body = json.loads(result.stdout)
    except (ValueError, AttributeError):
        body = None
    return {
        "argv": ["todoc", "--root", "<temporary-root>", *args],
        "exit_code": result.exit_code,
        "exception": repr(result.exception) if result.exception else None,
        "envelope": body,
    }


def fresh(base, name):
    root = base / name
    result = invoke(root, "init", "--root", str(root))
    assert result["exit_code"] == 0, result
    return root


results = {}
with tempfile.TemporaryDirectory(prefix="todoc-audit-") as directory:
    base = Path(directory)
    root = fresh(base, "traversal")
    outside = base / "outside.md"
    outside.write_text("# Outside\n\nOriginal.\n")
    opened = invoke(root, "change", "open", "--title", "Traversal")
    assert opened["exit_code"] == 0, opened
    delta = root / "changes" / "traversal" / "deltas" / "audit.md"
    delta.write_text("---\ntarget: ../outside.md\norder: 1\n---\n\n## ADDED: ## Injected\n\nAudit content.\n")
    results["delta_outside_validate"] = invoke(root, "change", "validate", "traversal")
    results["delta_outside_apply"] = invoke(root, "change", "apply", "traversal", "--apply")
    results["delta_outside_content"] = {"outside_modified": "Audit content." in outside.read_text()}

    root = fresh(base, "relation")
    (root / "bad.json").write_text(json.dumps({
        "record_id": "note:bad", "entity_type": "note", "title": "bad",
        "relations": [{"type_id": "references", "target": "bad-target"}],
    }))
    results["malformed_relation"] = invoke(root, "validate", "--all")

    root = fresh(base, "encoding")
    (root / "bad.md").write_bytes(b"# bad\n\xff")
    results["invalid_utf8_validate"] = invoke(root, "validate", "--all")
    results["invalid_utf8_search"] = invoke(root, "docs", "search", "--query", "bad")

    root = fresh(base, "edit")
    assert invoke(root, "docs", "new", "--path", "note.md", "--title", "test")["exit_code"] == 0
    patch_file = base / "patch.json"
    patch_file.write_text(json.dumps({"ops": [{"line": "not-an-integer", "text": "new"}]}))
    results["invalid_patch_preview"] = invoke(root, "docs", "edit", "--id", "doc:note.md", "--patch-file", str(patch_file), "--preview")
    results["invalid_patch_apply"] = invoke(root, "docs", "edit", "--id", "doc:note.md", "--patch-file", str(patch_file), "--apply")
    results["zero_limit_search"] = invoke(root, "docs", "search", "--query", "test", "--limit", "0")
    results["zero_limit_search_again"] = invoke(root, "docs", "search", "--query", "test", "--limit", "0", "--cursor", "0")
    assert invoke(root, "docs", "new", "--path", "note2.md", "--title", "test two")["exit_code"] == 0
    results["positive_pagination_first"] = invoke(root, "docs", "search", "--query", "test", "--limit", "1")
    results["positive_pagination_second"] = invoke(root, "docs", "search", "--query", "test", "--limit", "1", "--cursor", "1")
    (root / "data.csv").write_text("key,value\nno,first\nyes,second\n")
    results["csv_filter_before_limit"] = invoke(root, "docs", "read", "--id", "doc:data.csv", "--rows", "1", "--where", "key=yes")

    root = fresh(base, "race")
    target = root / "record.json"
    plan = WritePlan(dataset_id="audit", target_path="record.json", new_content="first writer\n", expected_hash=None, new_hash="unused", basis="audit", validations=())

    def interleave(path, content):
        # A second writer creates the path after the first writer's existence check.
        path.write_text("second writer\n")
        atomic_write(path, content)

    with patch("todoc.application.write.atomic_write", side_effect=interleave):
        outcome = apply_write_plan(root, plan)
    results["create_only_race"] = {"returned": outcome, "final_content": target.read_text(), "competing_content_lost": target.read_text() != "second writer\n", "method": "deterministic interleaving at atomic_write; no concurrent process"}

    root = fresh(base, "snapshot")
    store = RegistryStore(root)
    store.publish({"dataset_id": "audit"}, [], [], [], [], [])
    before = store.load_current() is not None
    original_rename = Path.rename

    def fail_publish(path, destination):
        if path.name == ".tmp-current":
            raise OSError("audit injected rename failure")
        return original_rename(path, destination)

    try:
        with patch.object(Path, "rename", fail_publish):
            store.publish({"dataset_id": "audit"}, [], [], [], [], [])
    except OSError as error:
        failure = str(error)
    results["snapshot_failure"] = {"before_readable": before, "failure": failure, "after_readable": store.load_current() is not None, "current_dir_exists": store.current_dir.exists(), "method": "injected failure at staging-directory rename"}

actual_leaves = []


def walk(group, prefix=()):
    for name, command in group.commands.items():
        if isinstance(command, click.Group):
            walk(command, prefix + (name,))
        else:
            actual_leaves.append(prefix + (name,))


walk(cli)
contract_inventory = []
for name, command in cli.commands.items():
    if isinstance(command, click.Group):
        contract_inventory.extend((name, sub) for sub in command.commands)
    else:
        contract_inventory.append((name,))
results["contract_inventory"] = {
    "actual_leaves": len(actual_leaves), "contract_inventory": len(contract_inventory),
    "missing": sorted(set(actual_leaves) - set(contract_inventory)),
    "nonleaves": sorted(set(contract_inventory) - set(actual_leaves)),
}

print(json.dumps(results, ensure_ascii=False, indent=2))
