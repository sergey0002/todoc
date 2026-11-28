#!/usr/bin/env python3
"""Acceptance matrix for the open bug backlog (read-only on the live dataset).

Run from the repository root:

    env PYTHONPATH=src python3 tools/bug_acceptance.py --root demo
    env PYTHONPATH=src python3 tools/bug_acceptance.py --root demo --only BUG-034-change
    env PYTHONPATH=src python3 tools/bug_acceptance.py --root demo --gate

Every mutating probe runs in a throwaway ``tempfile.TemporaryDirectory``; the
live dataset is only read. Each row is bound to the report path (``doc_id``) so
two reports sharing a number stay distinct. ``--only`` selects probes *before*
they run. ``--gate`` fails on inventory gaps, unknown or duplicate report paths,
probe errors and ``fixed`` rows without evidence.

Statuses: ``fixed`` / ``open`` / ``stale`` / ``duplicate`` / ``manual`` /
``not_applicable`` / ``unverified`` / ``error``. ``unverified`` means a probe
only saw a proxy signal (a file exists, a string is present); it must never be
promoted to ``fixed`` without the report's own scenario.

This is a planning aid, not a product: it is not imported by ``todoc`` and it
does not change any dataset. Keep it in sync with ``demo/bugs/`` when a probe
stops matching the report.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

ENV = {**os.environ, "PYTHONPATH": str(REPO / "src")}

FIXED = "fixed"
OPEN = "open"
STALE = "stale"
DUPLICATE = "duplicate"
MANUAL = "manual"
NOT_APPLICABLE = "not_applicable"
UNVERIFIED = "unverified"
ERROR = "error"

TERMINAL_REPORT_STATUSES = {"fixed", "wontfix", "duplicate"}


def call(root: Path, *args: str) -> tuple[int, dict | None, str]:
    return call_args([*args, "--root", str(root)])


def call_args(args: list[str]) -> tuple[int, dict | None, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "todoc", *args],
        cwd=str(REPO), env=ENV, capture_output=True, text=True,
    )
    try:
        return proc.returncode, json.loads(proc.stdout), proc.stderr
    except (ValueError, TypeError):
        return proc.returncode, None, proc.stderr


def codes(body: dict | None) -> list[str]:
    return [item.get("code", "") for item in (body or {}).get("diagnostics") or []]


def meta(body: dict | None) -> dict:
    return ((body or {}).get("data") or {}).get("meta") or {}


def result(body: dict | None) -> dict:
    return ((body or {}).get("data") or {}).get("result") or {}


def fresh(base: Path, name: str = "root") -> Path:
    root = base / name
    code, body, err = call(root, "init", "--apply")
    if code != 0:
        raise RuntimeError(f"init failed: {code} {codes(body)} {err[:200]}")
    return root


@dataclass
class Ctx:
    live: Path
    base: Path
    _temp_root: Path | None = field(default=None, repr=False)

    def fresh(self, name: str) -> Path:
        return fresh(self.base, name)

    def temp_root(self) -> Path:
        if self._temp_root is None:
            self._temp_root = fresh(self.base, "shared")
        return self._temp_root


@dataclass(frozen=True)
class Probe:
    key: str
    doc_id: str
    platform: str
    fn: Callable[[Ctx], tuple[str, str]]


# --- live probes (read-only) -------------------------------------------------


def probe_bug_015(ctx: Ctx) -> tuple[str, str]:
    from todoc.adapters.formats.markdown import parse_markdown

    doc = parse_markdown('---\ntitle: "a \\"b\\" c"\ndoc_type: note\n---\n\n# x\n')
    title = (doc.front_matter or {}).get("title")
    return (FIXED if title == 'a "b" c' else OPEN, f"yaml escape title={title!r}")


def probe_bug_017(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "docs", "tree", "--limit", "5")
    m = meta(body)
    ok = code == 0 and m.get("truncated") is True and bool(m.get("next_cursor"))
    return (FIXED if ok else OPEN,
            f"tree limit=5 total={m.get('total')} returned={m.get('returned')} truncated={m.get('truncated')}")


def probe_bug_018(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "docs", "read", "--id", "doc:home", "--budget", "100")
    r = result(body)
    text = r.get("text") or ""
    ok = code == 0 and len(text) <= 140 and r.get("truncated") is True
    return (FIXED if ok else OPEN, f"read --budget 100 text_len={len(text)} truncated={r.get('truncated')}")


def probe_bug_019(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "docs", "search", "--query", "", "--limit", "2")
    ok = code == 2 and "usage.error" in codes(body)
    return (FIXED if ok else OPEN, f"empty query exit={code} codes={codes(body)}")


def probe_bug_020(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "records", "list", "--type", "bug-report", "--limit", "1")
    ok = code == 2 and "query.namespace_mismatch" in codes(body)
    return (FIXED if ok else OPEN, f"records list doc_type exit={code} codes={codes(body)}")


def probe_bug_021(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "explain-path", "demo/skill/doc-spec-write/SKILL.md")
    diag = ((body or {}).get("diagnostics") or [{}])[0]
    ok = code != 0 and bool(diag.get("suggested_fixes"))
    return (FIXED if ok else OPEN, f"path_not_found exit={code} suggested_fixes={diag.get('suggested_fixes')}")


def probe_bug_024(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "docs", "list", "--type", "unknown",
                         "--origin", "document", "--limit", "1000")
    total = meta(body).get("total")
    ok = code == 0 and total == 0
    return (FIXED if ok else OPEN, f"docs list --type unknown --origin document exit={code} total={total}")


def probe_bug_026(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "doctor", "--scope", "environment")
    checks = (result(body).get("datasets") or [{}])[0].get("checks") or []
    ids = {c.get("id") for c in checks}
    required = {"entrypoint", "python", "venv", "encoding", "data_root"}
    statuses = {c.get("status") for c in checks}
    ok = code == 0 and required <= ids and statuses <= {"pass", "fail", "warn"}
    return (FIXED if ok else OPEN,
            f"doctor environment checks={sorted(ids)} statuses={sorted(map(str, statuses))}")


def probe_bug_029(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "skills", "tree", "--vault", "all", "--limit", "1000")
    rows = result(body).get("skills") or []
    vaults = {row.get("vault") for row in rows}
    ok = code == 0 and {"skills", "skill"} <= vaults
    return (FIXED if ok else OPEN, f"skills tree --vault all exit={code} vaults={sorted(map(str, vaults))}")


def probe_bug_037(ctx: Ctx) -> tuple[str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "todoc", "--output", "table", "docs", "list",
         "--type", "ghost", "--root", str(ctx.live)],
        cwd=str(REPO), env=ENV, capture_output=True, text=True,
    )
    first = (proc.stdout or "").lstrip()[:1]
    ok = proc.returncode == 2 and first not in ("{", "[")
    return (FIXED if ok else OPEN,
            f"global --output table error path exit={proc.returncode} first_char={first!r}")


def probe_bug_038(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "records", "list", "--type", "task", "--limit", "1")
    rid = (result(body).get("items") or [{}])[0].get("record_id")
    if not rid:
        return (MANUAL, "no task record in dataset")
    code, body, _ = call(ctx.live, "records", "read", "--id", rid, "--view", "nope")
    ok = "view.fallback" in codes(body)
    return (FIXED if ok else OPEN, f"records read --view nope codes={codes(body)}")


def probe_bug_039(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "records", "aggregate", "--metric", "volume", "--group-by", "date")
    discovery = ((body or {}).get("data") or {}).get("executed") is False
    ok = discovery or (code == 2 and "usage.error" in codes(body))
    return (FIXED if ok else OPEN,
            f"aggregate without --type exit={code} discovery={discovery} codes={codes(body)}")


def probe_bug_040(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "skills", "read", "--path", "coding/git/commit-message",
                         "--line-range", "5-1")
    range_ok = code == 3 and "usage.invalid_line_range" in codes(body)
    code2, body2, _ = call(ctx.live, "skills", "read", "--path", "coding/git/commit-message",
                           "--budget", "-1")
    budget_ok = code2 == 2 and "usage.error" in codes(body2)
    ok = range_ok and budget_ok
    return (FIXED if ok else OPEN,
            f"bad range exit={code} codes={codes(body)}; budget -1 exit={code2} codes={codes(body2)}")


def probe_bug_043(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "docs", "read", "--id", "doc:home", "--line-range", "9999-10000")
    ok = code == 3 and "usage.invalid_line_range" in codes(body)
    return (FIXED if ok else OPEN, f"line-range out of bounds exit={code} codes={codes(body)}")


def probe_bug_045(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "docs", "search", "--query", "и", "--budget", "50", "--limit", "10")
    budget = meta(body).get("budget")
    used = (budget or {}).get("used_bytes")
    exhausted = (budget or {}).get("exhausted")
    measured = len(json.dumps(body, ensure_ascii=False).encode("utf-8")) if body else 0
    ok = (code == 0 and isinstance(budget, dict) and isinstance(used, int)
          and used <= 50 and exhausted is True and measured >= used)
    return (FIXED if ok else OPEN,
            f"budget={budget} measured_utf8={measured} response_chars={len(json.dumps(body or {}))}")


def probe_bug_049(ctx: Ctx) -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="acc-patch-") as patch_dir:
        bad = Path(patch_dir) / "bad.json"
        bad.write_text(json.dumps({"ops": [{"op": "explode", "line": 1}]}), encoding="utf-8")
        code, body, _ = call(ctx.live, "docs", "edit", "--id", "doc:home",
                             "--patch-file", str(bad), "--preview")
    ok = code == 3 and "edit.op_unknown" in codes(body)
    return (FIXED if ok else OPEN, f"invalid op exit={code} codes={codes(body)}")


def probe_bug_050(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "docs", "search", "--query", "x", "--limit", "0")
    ok = code == 2 and "usage.error" in codes(body)
    return (FIXED if ok else OPEN, f"limit 0 exit={code} codes={codes(body)}")


def probe_bug_055(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "docs", "search", "--type", "ghost", "--limit", "2")
    type_ok = code == 2 and "docs.unknown_type" in codes(body)
    code2, body2, _ = call(ctx.live, "docs", "search", "--query", "x", "--within",
                            "no/such/dir", "--limit", "2")
    scope_ok = code2 == 2 and "usage.path_not_found" in codes(body2)
    return (FIXED if type_ok and scope_ok else OPEN,
            f"unknown type exit={code} codes={codes(body)}; missing scope exit={code2} "
            f"codes={codes(body2)}")


def probe_bug_056(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "tags", "list")
    ok = code == 0 and bool(result(body).get("items"))
    return (FIXED if ok else OPEN, f"tags list exit={code} codes={codes(body)}")


def probe_bug_057(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "docs", "search", "--type", "bug-report",
                         "--fields", "path,status", "--limit", "1")
    search_status = code == 0 and bool(result(body).get("items"))
    code2, body2, _ = call(ctx.live, "docs", "list", "--type", "bug-report", "--origin", "document",
                           "--status", "open", "--limit", "1", "--fields", "path,status,origin")
    origin_ok = code2 == 0 and meta(body2).get("total") is not None
    code3, body3, _ = call(ctx.live, "docs", "list", "--type", "ghost", "--limit", "1")
    unknown_ok = code3 == 2 and "docs.unknown_type" in codes(body3)
    ok = search_status and origin_ok and unknown_ok
    return (FIXED if ok else OPEN,
            f"search status={search_status} origin={origin_ok} unknown_type={unknown_ok}")


def probe_bug_060(ctx: Ctx) -> tuple[str, str]:
    code, body, _ = call(ctx.live, "docs", "list", "--type", "idea",
                         "--status", "captured|planned", "--limit", "1000")
    pipe_total = meta(body).get("total")
    code2, body2, _ = call(ctx.live, "docs", "list", "--type", "idea",
                           "--status", "captured", "--status", "planned", "--limit", "1000")
    repeated_total = meta(body2).get("total")
    ok = (code == 0 and code2 == 0 and isinstance(pipe_total, int) and pipe_total > 0
          and pipe_total == repeated_total)
    return (FIXED if ok else OPEN,
            f"status pipe total={pipe_total} repeated total={repeated_total}")


# --- isolated probes (temp dataset) -----------------------------------------


def probe_bug_013(ctx: Ctx) -> tuple[str, str]:
    root = ctx.fresh("docs-new")
    code, body, _ = call(root, "docs", "new", "--type", "note", "--title", "T", "--apply")
    r = result(body)
    doc_id = r.get("id")
    saved = code == 0 and doc_id == f"doc:{r.get('path')}" and "record_id" in r
    read_code, read_body, _ = call(root, "docs", "read", "--id", doc_id or "doc:absent")
    readable = read_code == 0 and result(read_body).get("resolved_from") is None
    return (FIXED if saved and readable else OPEN,
            f"docs new id={doc_id!r} record_id={r.get('record_id')!r}; read exit={read_code}")


def probe_bug_014(ctx: Ctx) -> tuple[str, str]:
    root = ctx.fresh("edit-preview")
    code, body, _ = call(root, "docs", "new", "--type", "note", "--title", "T", "--apply")
    doc_id = result(body).get("id") or "doc:home"
    with tempfile.TemporaryDirectory(prefix="acc-patch-") as patch_dir:
        patch = Path(patch_dir) / "p.json"
        patch.write_text(json.dumps({"ops": [{"op": "insert_after", "line": 1, "text": "X"}]}),
                         encoding="utf-8")
        code, body, _ = call(root, "docs", "edit", "--id", doc_id,
                             "--patch-file", str(patch), "--preview")
    numbered = result(body).get("numbered")
    ok = (code == 0 and isinstance(numbered, list) and bool(numbered)
          and numbered[0].get("line") == 1 and "text" in numbered[0])
    return (FIXED if ok else OPEN, f"edit preview keys={sorted(result(body))} numbered={type(numbered).__name__}")


def probe_bug_027(ctx: Ctx) -> tuple[str, str]:
    root = ctx.fresh("skills-root")
    skills = root / "skills"
    (skills / "child").mkdir(parents=True, exist_ok=True)
    (skills / "SKILL.md").write_text("---\nname: root\ndescription: Root skill\n---\n", encoding="utf-8")
    (skills / "child" / "SKILL.md").write_text(
        "---\nname: child\ndescription: Child skill\n---\n", encoding="utf-8")
    code, body, _ = call(root, "skills", "tree")
    paths = {row.get("path") for row in result(body).get("skills") or []}
    ok = code == 0 and "child" in paths
    return (FIXED if ok else OPEN, f"root SKILL.md exit={code} skills={sorted(map(str, paths))}")


def probe_bug_034_change(ctx: Ctx) -> tuple[str, str]:
    from unittest import mock

    import todoc.application.changes as changes

    root = ctx.fresh("containment")
    outside = ctx.base / "outside-sentinel.md"
    outside.write_text("SECRET-OUTSIDE", encoding="utf-8")
    code, body, _ = call(root, "change", "open", "--title", "Boundary", "--apply")
    cid = result(body).get("change_id")
    if not cid:
        return (ERROR, f"change open failed: exit={code} codes={codes(body)}")
    folder = root / "changes" / cid.split(":", 1)[-1] / "deltas"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "evil.md").write_text(
        "---\ntarget: ../outside-sentinel.md\ndoc_type: delta\n---\n\n# D\n\n## ADDED: X\n\nPWNED\n",
        encoding="utf-8")
    reads: list[str] = []
    real_hash = changes.file_hash
    real_read_text = Path.read_text

    def guarded_hash(path):
        resolved = Path(path).resolve()
        if resolved == outside.resolve():
            reads.append(str(resolved))
            return "sha256:deadbeef"
        return real_hash(path)

    def guarded_read_text(self, *args, **kwargs):
        if self.resolve() == outside.resolve():
            reads.append(str(self.resolve()))
            return "SECRET-OUTSIDE"
        return real_read_text(self, *args, **kwargs)

    with mock.patch.object(changes, "file_hash", guarded_hash), \
            mock.patch.object(Path, "read_text", guarded_read_text):
        diags = changes.validate_change(root, cid)
    code2, body2, _ = call(root, "change", "apply", cid, "--apply")
    unchanged = outside.read_text(encoding="utf-8") == "SECRET-OUTSIDE"
    codes2 = codes(body2)
    if reads:
        return (OPEN, f"delta target outside root was read: {reads[0]}")
    if [d.code for d in diags] != ["change.delta_target_outside_root"]:
        return (OPEN, f"unexpected validate diagnostics: {[d.code for d in diags]}")
    if code2 == 3 and "change.delta_target_outside_root" in codes2 and unchanged:
        return (FIXED, f"outside target refused with change.delta_target_outside_root; apply exit={code2}")
    return (OPEN, f"outside read blocked but apply exit={code2} codes={codes2}")


def probe_bug_035_history(ctx: Ctx) -> tuple[str, str]:
    root = ctx.temp_root()
    code, body, _ = call(root, "history", "show", "--path", "notes/a.md")
    old_gone = code == 2 and "usage.error" in codes(body)
    code2, body2, _ = call(root, "show", "--path", "../outside.md")
    successors_refuse = code2 == 2 and "docs.invalid_scope" in codes(body2)
    ok = old_gone and successors_refuse
    return (FIXED if ok else OPEN,
            f"nested history show exit={code}; successor show refuses escaping path exit={code2}")


def probe_bug_035_skills(ctx: Ctx) -> tuple[str, str]:
    return (DUPLICATE, "duplicate of bugs/bug-027-skills-tree-crash-on-root-skill-md.md")


def probe_bug_036(ctx: Ctx) -> tuple[str, str]:
    root = ctx.temp_root()
    src = ctx.base / "skill-import"
    src.mkdir(parents=True, exist_ok=True)
    (src / "SKILL.md").write_text("---\nname: x\ndescription: y\n---\n", encoding="utf-8")
    code, body, _ = call(root, "skills", "import", "--src", str(src), "--into", "../escaped", "--apply")
    ok = (code == 2 and "docs.invalid_scope" in codes(body)
          and not (ctx.base / "escaped").exists())
    return (FIXED if ok else OPEN,
            f"skills import --into ../escaped exit={code} codes={codes(body)}")


def probe_bug_041(ctx: Ctx) -> tuple[str, str]:
    root = ctx.fresh("filters")
    workouts = root / "records" / "workouts"
    workouts.mkdir(parents=True, exist_ok=True)
    for name, day in (("a", "2026-11-30"), ("b", "2026-11-20"), ("c", "2026-11-20"), ("d", "2026-11-21")):
        (workouts / f"{name}.json").write_text(json.dumps({
            "schema_version": 1, "record_id": f"workout:{name}", "entity_type": "workout",
            "date": day, "volume": {"value": 10, "unit": "kg"}}), encoding="utf-8")
    call(root, "index", "rebuild")
    code, body, _ = call(root, "records", "list", "--type", "workout",
                         "--since", "2026-11-20", "--until", "2026-11-21", "--limit", "1")
    m = meta(body)
    ok = m.get("total") == 3 and m.get("returned") == 1
    return (FIXED if ok else OPEN,
            f"filters before limit total={m.get('total')} returned={m.get('returned')}")


def probe_bug_042(ctx: Ctx) -> tuple[str, str]:
    root = ctx.temp_root()
    with tempfile.TemporaryDirectory(prefix="acc-spec-") as spec_dir:
        spec = Path(spec_dir) / "query.json"
        spec.write_text(json.dumps({"filters": {"tags": ["a"]}}), encoding="utf-8")
        code, body, _ = call(root, "records", "query", "--query-file", str(spec))
    ok = code in (2, 3) and "query.invalid_file" in codes(body)
    return (FIXED if ok else OPEN, f"invalid QuerySpec exit={code} codes={codes(body)}")


def probe_bug_044(ctx: Ctx) -> tuple[str, str]:
    root = ctx.fresh("no-index")
    shutil.rmtree(root / ".todoc" / "index", ignore_errors=True)
    code, body, _ = call(root, "status")
    actions = (body or {}).get("next_actions") or []
    ok = code == 0 and bool(actions) and all("argv" in a and "purpose" in a for a in actions)
    return (FIXED if ok else OPEN, f"status without index next_actions={actions}")


def probe_bug_046(ctx: Ctx) -> tuple[str, str]:
    root = ctx.fresh("fix-link")
    notes = root / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / "runbook.md").write_text("---\ntitle: Runbook\ndoc_type: note\n---\n\n# Runbook\n",
                                      encoding="utf-8")
    source = notes / "a.md"
    source.write_text(
        "---\ntitle: A\ndoc_type: note\n---\n\n"
        "В тексте уже упомянут runbok.md как пример опечатки.\n\n"
        "Ссылка: [runbook](runbok.md).\n",
        encoding="utf-8")
    code, body, _ = call(root, "validate", "--all")
    target = None
    for diag in (body or {}).get("diagnostics") or []:
        if diag.get("code") == "markdown.link.target_missing" and diag.get("id"):
            target = diag
            break
    if target is None:
        return (ERROR, "no link diagnostic produced for the fixture")
    fix = next((item for item in target.get("suggested_fixes") or []
                if item.get("kind") == "replace_link_target"), None)
    if fix is None:
        return (OPEN, f"no replace_link_target suggestion: {target.get('suggested_fixes')}")
    code, body, _ = call(root, "fix", "--diagnostic", target["id"], "--apply")
    after = source.read_text(encoding="utf-8")
    link_fixed = "](runbok.md)" not in after and "](runbook.md)" in after
    prose_kept = "runbok.md как пример опечатки" in after
    code2, body2, _ = call(root, "validate", "--all")
    clean = not any(c == "markdown.link.target_missing" for c in codes(body2))
    ok = code == 0 and link_fixed and prose_kept and clean
    return (FIXED if ok else OPEN,
            f"fix exit={code} link_replaced={link_fixed} prose_kept={prose_kept} revalidate_clean={clean}")


def probe_bug_047(ctx: Ctx) -> tuple[str, str]:
    root = ctx.fresh("relations")
    (root / "r.json").write_text(json.dumps({
        "schema_version": 1, "record_id": "task:x", "entity_type": "task",
        "relations": [{"type_id": "implements", "target": "not-an-object"}]}), encoding="utf-8")
    code, body, _ = call(root, "validate", "--all")
    ok = any(c.startswith("relation.") for c in codes(body))
    return (FIXED if ok else OPEN, f"malformed relation codes={codes(body)[:4]}")


def probe_bug_048(ctx: Ctx) -> tuple[str, str]:
    root = ctx.fresh("utf8")
    (root / "bad.md").write_bytes(b"# Bad \xff\xfe\n")
    call(root, "index", "rebuild")
    code, body, _ = call(root, "docs", "search", "--query", "Bad")
    ok = code in (0, 6) and "file.unreadable" in codes(body)
    return (FIXED if ok else OPEN, f"invalid utf8 exit={code} codes={codes(body)}")


def probe_bug_051(ctx: Ctx) -> tuple[str, str]:
    from todoc.adapters.filesystem.scanner import atomic_write

    with tempfile.TemporaryDirectory(prefix="acc-create-") as tmp:
        target = Path(tmp) / "x.json"
        target.write_text("first", encoding="utf-8")
        try:
            atomic_write(target, "second", exclusive=True)
        except FileExistsError:
            unchanged = target.read_text(encoding="utf-8") == "first"
            return (FIXED if unchanged else OPEN,
                    f"FileExistsError raised; target unchanged={unchanged}")
        return (OPEN, "exclusive atomic_write overwrote an existing target")


def probe_bug_052(ctx: Ctx) -> tuple[str, str]:
    from unittest import mock

    from todoc.application.registry import RegistryStore

    with tempfile.TemporaryDirectory(prefix="acc-publish-") as tmp:
        store = RegistryStore(Path(tmp))
        store.publish({"dataset_id": "old"}, [], [], [], [], [])
        real_rename = Path.rename
        raised = False

        def failing_rename(self, target):
            if self.name == "staged":
                raise OSError("injected rename failure")
            return real_rename(self, target)

        with mock.patch.object(Path, "rename", failing_rename):
            try:
                store.publish({"dataset_id": "new"}, [], [], [], [], [])
            except OSError:
                raised = True
        payload = store.load_current()
        restored = bool(payload) and payload.get("dataset_id") == "old"
        return (FIXED if raised and restored else OPEN,
                f"failure_raised={raised} previous_generation_restored={restored}")


def probe_bug_053(ctx: Ctx) -> tuple[str, str]:
    node_ids = [
        "tests/cli/test_cli_contract.py::test_every_leaf_command_is_covered",
        "tests/cli/test_cli_contract.py::test_inventory_preserves_public_option_grammar",
    ]
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", *node_ids],
                          cwd=str(REPO), env=ENV, capture_output=True, text=True)
    return (FIXED if proc.returncode == 0 else OPEN,
            f"contract inventory tests exit={proc.returncode}")


# --- static probes (never promoted to fixed) --------------------------------


def probe_bug_023(ctx: Ctx) -> tuple[str, str]:
    exists = (REPO / "tools" / "todoc-wsl.sh").is_file()
    return (UNVERIFIED if exists else OPEN,
            "tools/todoc-wsl.sh present; argv contract not executed" if exists
            else "no harness entrypoint")


def probe_bug_028(ctx: Ctx) -> tuple[str, str]:
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    present = "внешние одинарные кавычки" in agents
    return (UNVERIFIED if present else OPEN,
            "AGENTS.md phrase present; runtime contract not executed" if present
            else "AGENTS.md runtime contract missing")


def probe_bug_058(ctx: Ctx) -> tuple[str, str]:
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    mounted = (REPO / ".kilo" / "skills" / "todoc" / "SKILL.md").is_file()
    present = "docs list --type" in agents and mounted
    return (UNVERIFIED if present else OPEN,
            "route strings present; published examples not executed" if present
            else "AGENTS.md route or mounted dispatcher missing")


def manual(evidence: str) -> Callable[[Ctx], tuple[str, str]]:
    return lambda ctx: (MANUAL, evidence)


def windows_only(evidence: str) -> Callable[[Ctx], tuple[str, str]]:
    return lambda ctx: (NOT_APPLICABLE, evidence)


def probe_registry() -> list[Probe]:
    return [
        Probe("BUG-011", "bugs/bug-011-dreyf-derived-from-pri-smene-statusa-tela-ishodnika-trebuet-ruchnogo-re-ankoringa.md", "any", manual("blocked by demo/plan/bmad-wave-planning-skills.md")),
        Probe("BUG-013", "bugs/bug-013-neodnorodnye-id-i-output-kontrakty-rezolv-identifikatora-trebuet-ruchnogo-grep.md", "any", probe_bug_013),
        Probe("BUG-014", "bugs/bug-014-docs-edit-preview-ne-pokazyvaet-numeraciyu-rezultata.md", "any", probe_bug_014),
        Probe("BUG-015", "bugs/bug-015-yaml-lite-front-matter-ne-obrabatyvaet-backslash-escape-kavychek.md", "any", probe_bug_015),
        Probe("BUG-016", "bugs/bug-016-filtry-records-query-ne-dokumentirovany-v-spravkah.md", "any", manual("docs: compare operators, nested lists and example with application/query.py")),
        Probe("BUG-017", "bugs/bug-017-docs-tree-silent-truncation.md", "any", probe_bug_017),
        Probe("BUG-018", "bugs/bug-018-docs-read-full-ignores-budget.md", "any", probe_bug_018),
        Probe("BUG-019", "bugs/bug-019-docs-search-empty-query.md", "any", probe_bug_019),
        Probe("BUG-020", "bugs/bug-020-records-list-wrong-namespace.md", "any", probe_bug_020),
        Probe("BUG-021", "bugs/bug-021-usage-errors-without-guidance.md", "any", probe_bug_021),
        Probe("BUG-023", "bugs/bug-023-cli-not-reachable-from-harness.md", "any", probe_bug_023),
        Probe("BUG-024", "bugs/bug-024-skills-noise-no-todocignore.md", "any", probe_bug_024),
        Probe("BUG-025", "bugs/bug-025-idea-plan-deferral-unlinked.md", "any", manual("docs: action-logging <-> release decision backlinks")),
        Probe("BUG-026", "bugs/bug-026-doctor-environment-checks-hardcoded-pass.md", "any", probe_bug_026),
        Probe("BUG-027", "bugs/bug-027-skills-tree-crash-on-root-skill-md.md", "any", probe_bug_027),
        Probe("BUG-028", "bugs/bug-028-no-runtime-contract-for-windows-wsl-harness.md", "any", probe_bug_028),
        Probe("BUG-029", "bugs/bug-029-two-skill-stores-no-unified-listing.md", "any", probe_bug_029),
        Probe("BUG-030", "bugs/bug-030-unicode-encode-error-windows-stdout.md", "windows", windows_only("Windows-only: needs a Windows run")),
        Probe("BUG-031", "bugs/bug-031-windows-path-separator-test-failure.md", "windows", windows_only("Windows-only: needs a Windows run")),
        Probe("BUG-032", "bugs/bug-032-cli-returns-windows-paths-with-backslash.md", "windows", windows_only("Windows-only: needs a Windows run")),
        Probe("BUG-033", "bugs/bug-033-history-revert-line-endings-windows.md", "windows", windows_only("Windows-only: needs a Windows run")),
        Probe("BUG-034-change", "bugs/bug-034-change-apply-target-outside-root.md", "any", probe_bug_034_change),
        Probe("BUG-034-windows", "bugs/bug-034-history-tests-windows-chmod-line-endings.md", "windows", windows_only("Windows-only: needs a Windows run")),
        Probe("BUG-035-history", "bugs/bug-035-history-path-outside-root.md", "any", probe_bug_035_history),
        Probe("BUG-035-skills", "bugs/bug-035-skills-tree-crash-root-skill-md.md", "any", probe_bug_035_skills),
        Probe("BUG-036", "bugs/bug-036-skills-import-outside-root.md", "any", probe_bug_036),
        Probe("BUG-037", "bugs/bug-037-global-output-ignored.md", "any", probe_bug_037),
        Probe("BUG-038", "bugs/bug-038-records-read-unknown-view.md", "any", probe_bug_038),
        Probe("BUG-039", "bugs/bug-039-records-aggregate-hidden-default.md", "any", probe_bug_039),
        Probe("BUG-040", "bugs/bug-040-skills-read-invalid-range.md", "any", probe_bug_040),
        Probe("BUG-041", "bugs/bug-041-records-list-post-limit-filters.md", "any", probe_bug_041),
        Probe("BUG-042", "bugs/bug-042-records-query-invalid-spec.md", "any", probe_bug_042),
        Probe("BUG-043", "bugs/bug-043-docs-read-line-range-out-of-bounds.md", "any", probe_bug_043),
        Probe("BUG-044", "bugs/bug-044-status-next-actions-contract.md", "any", probe_bug_044),
        Probe("BUG-045", "bugs/bug-045-docs-search-budget-not-honest.md", "any", probe_bug_045),
        Probe("BUG-046", "bugs/bug-046-fix-applies-wrong-occurrence.md", "any", probe_bug_046),
        Probe("BUG-047", "bugs/bug-047-malformed-relation-target.md", "any", probe_bug_047),
        Probe("BUG-048", "bugs/bug-048-invalid-utf8-search-crash.md", "any", probe_bug_048),
        Probe("BUG-049", "bugs/bug-049-edit-preview-invalid-ops.md", "any", probe_bug_049),
        Probe("BUG-050", "bugs/bug-050-zero-limit-search-cursor.md", "any", probe_bug_050),
        Probe("BUG-051", "bugs/bug-051-create-only-concurrent-overwrite.md", "any", probe_bug_051),
        Probe("BUG-052", "bugs/bug-052-index-publish-loses-snapshot.md", "any", probe_bug_052),
        Probe("BUG-053", "bugs/bug-053-contract-tests-missing-nested-leaves.md", "any", probe_bug_053),
        Probe("BUG-054", "bugs/bug-054-current-docs-search-csv-drift.md", "any", manual("docs: compare pagination, read-only, CSV filter with code")),
        Probe("BUG-055", "bugs/bug-055-unknown-search-filter-silent-empty.md", "any", probe_bug_055),
        Probe("BUG-056", "bugs/bug-056-no-tag-listing-or-record-filter.md", "any", probe_bug_056),
        Probe("BUG-057", "bugs/bug-057-open-bugs-list-not-discoverable.md", "any", probe_bug_057),
        Probe("BUG-058", "bugs/bug-058-routing-docs-gap.md", "any", probe_bug_058),
        Probe("BUG-059", "bugs/bug-059-refresh-demo-state-broken.md", "any", manual("tooling: run tools/refresh_demo_state.py on a copy after 3.9")),
        Probe("BUG-060", "bugs/bug-060-status-filter-pipe-rejected.md", "any", probe_bug_060),
        Probe("DESIGN-Q01", "bugs/design-q01-terminalnyy-status-zapisi-guard-procedurnyy-dvizhok-molchit.md", "any", manual("decision required: records status transition policy")),
        Probe("DESIGN-Q02", "bugs/design-q02-review-first-dvoynoy-vyzov-stoimost-dlya-agenta-protiv-kontrolya.md", "any", manual("decision required: review-first cost vs control")),
    ]


# --- selection, inventory, gate ---------------------------------------------


def normalize_token(token: str) -> str:
    token = token.strip().upper()
    return token if token.startswith(("BUG-", "DESIGN-")) else f"BUG-{token}"


def usage_error(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def select_probes(probes: list[Probe], only: str) -> list[Probe]:
    tokens = [normalize_token(item) for item in only.split(",") if item.strip()]
    if not tokens:
        return probes
    chosen: list[Probe] = []
    for token in tokens:
        exact = [probe for probe in probes if probe.key.upper() == token]
        if exact:
            chosen.extend(exact)
            continue
        matches = [probe for probe in probes if probe.key.upper().startswith(token + "-")]
        if len(matches) == 1:
            chosen.extend(matches)
            continue
        if not matches:
            raise SystemExit(usage_error(f"unknown probe key: {token}"))
        raise SystemExit(usage_error(
            f"ambiguous probe key {token}: {', '.join(p.key for p in matches)}"))
    seen: set[str] = set()
    unique: list[Probe] = []
    for probe in chosen:
        if probe.key not in seen:
            seen.add(probe.key)
            unique.append(probe)
    return unique


def inventory(live: Path) -> dict[str, str]:
    code, body, err = call(live, "docs", "list", "--type", "bug-report", "--origin", "document",
                           "--file-format", "markdown", "--fields", "path,status",
                           "--limit", "1000")
    if code != 0 or body is None:
        raise SystemExit(f"inventory failed: exit={code} stderr={err[:200]}")
    if meta(body).get("truncated"):
        raise SystemExit("inventory is truncated; raise --limit")
    return {item["path"]: item.get("status") for item in result(body).get("items") or []}


def run_gate(live: Path, probes: list[Probe], rows: list[dict]) -> list[str]:
    problems: list[str] = []
    report = inventory(live)
    registry_ids = [probe.doc_id for probe in probes]
    duplicates = {doc_id for doc_id in registry_ids if registry_ids.count(doc_id) > 1}
    if duplicates:
        problems.append(f"duplicate report paths in registry: {sorted(duplicates)}")
    unknown = sorted(set(registry_ids) - set(report))
    if unknown:
        problems.append(f"registry paths absent from the dataset: {unknown}")
    uncovered = sorted(path for path, status in report.items()
                       if status not in TERMINAL_REPORT_STATUSES and path not in set(registry_ids))
    if uncovered:
        problems.append(f"non-terminal reports without a probe: {uncovered}")
    for row in rows:
        if row["status"] == ERROR:
            problems.append(f"{row['key']}: probe error: {row['evidence']}")
        if row["status"] == FIXED and not row["evidence"].strip():
            problems.append(f"{row['key']}: fixed without evidence")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Acceptance matrix for demo/bugs.")
    parser.add_argument("--root", default="demo", help="live dataset root (read-only)")
    parser.add_argument("--only", default="", help="comma-separated keys, e.g. BUG-020 or BUG-034-change")
    parser.add_argument("--gate", action="store_true", help="fail on inventory gaps and unconfirmed fixed rows")
    parser.add_argument("--json", action="store_true", help="emit the matrix as JSON")
    args = parser.parse_args()

    if args.gate and args.only.strip():
        parser.error("--gate requires a full run; drop --only")

    live = (REPO / args.root).resolve()
    probes = select_probes(probe_registry(), args.only)
    today = date.today().isoformat()
    host = platform.system().lower()
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="acc-temp-") as tmp:
        ctx = Ctx(live=live, base=Path(tmp))
        for probe in probes:
            try:
                status, evidence = probe.fn(ctx)
            except Exception as exc:  # a broken probe must not hide the rest
                status, evidence = ERROR, f"{type(exc).__name__}: {exc}"
            rows.append({"key": probe.key, "doc_id": probe.doc_id, "platform": probe.platform,
                         "status": status, "evidence": evidence, "date": today, "host": host})

    rows.sort(key=lambda row: row["key"])
    problems = run_gate(live, probes, rows) if args.gate else []

    if args.json:
        print(json.dumps({"date": today, "host": host, "rows": rows, "gate_problems": problems},
                         ensure_ascii=False, indent=2))
    else:
        width = max((len(row["key"]) for row in rows), default=6)
        print(f"# {today} host={host} probes={len(rows)}")
        print(f"{'BUG':<{width}}  {'PLATFORM':<8}  {'STATUS':<14}  EVIDENCE")
        for row in rows:
            print(f"{row['key']:<{width}}  {row['platform']:<8}  {row['status']:<14}  {row['evidence']}")
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        print("\n" + "  ".join(f"{key}={value}" for key, value in sorted(counts.items())))
        if problems:
            print("\nGATE FAILED:")
            for problem in problems:
                print(f"- {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
