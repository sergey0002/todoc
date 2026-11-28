#!/usr/bin/env python3
"""todoc quality benchmark.

Measures the CLI against explicit quality criteria (bench/criteria.md) on a
copy of the demo dataset, with seeded defects as ground truth, and runs the
competitor harnesses that are actually installed.

Usage:
    python3 bench/run_benchmark.py                 # full run
    python3 bench/run_benchmark.py --quick         # fewer latency repeats
    python3 bench/run_benchmark.py --venv /tmp/comp  # competitor venv

Outputs: bench/results/benchmark.json and bench/results/benchmark.md
Exit code: 0 if every criterion is pass/partial, 1 if any criterion failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from pathlib import Path, PureWindowsPath
from uuid import uuid4

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "demo"
RESULTS = REPO / "bench" / "results"

ENVELOPE_KEYS = {"schema_version", "ok", "data", "diagnostics", "next_actions"}

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def run_todoc(args: list[str], root: Path, expect_json: bool = True, *,
              prefix: tuple[str, ...] = (), environment: dict[str, str] | None = None) -> dict:
    """Run the todoc CLI, capturing stdout/stderr/exit code and parse time."""
    started = time.perf_counter()
    proc = subprocess.run(
        [*prefix, sys.executable, "-m", "todoc", *args],
        cwd=REPO,
        env={**(os.environ if environment is None else environment), "PYTHONPATH": str(REPO / "src")},
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - started
    out: dict = {
        "argv": ["todoc", *args],
        "exit_code": proc.returncode,
        "elapsed_s": round(elapsed, 3),
        "stdout_bytes": len(proc.stdout.encode()),
        "stderr_bytes": len(proc.stderr.encode()),
        "traceback": "Traceback (most recent call last)" in proc.stderr,
    }
    if expect_json and proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
            out["json_ok"] = isinstance(parsed, dict) and ENVELOPE_KEYS <= set(parsed)
            out["envelope"] = parsed
        except json.JSONDecodeError:
            out["json_ok"] = False
    else:
        out["json_ok"] = bool(not expect_json)
    return out


def _code_of(res: dict) -> str:
    """First diagnostic code of a call, or '' when the envelope carries none."""
    diags = (res.get("envelope") or {}).get("diagnostics") or []
    return str(diags[0].get("code", "")) if diags else ""


def sha256_files(root: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".todoc" in path.parts:
            continue
        digests[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def markdown_files(root: Path) -> list[Path]:
    return [p for p in sorted(root.rglob("*.md")) if ".todoc" not in p.parts]


def front_matter_of(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return {}
    out: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip().strip('"')
    return out


class Report:
    def __init__(self) -> None:
        self.criteria: list[dict] = []
        self.evidence: dict[str, object] = {}

    def add(self, cid: str, group: str, name: str, status: str, score: float,
            detail: str, evidence: object = None) -> None:
        self.criteria.append({"id": cid, "group": group, "name": name, "status": status,
                              "score": score, "detail": detail})
        if evidence is not None:
            self.evidence[cid] = evidence

    @property
    def total(self) -> float:
        return round(sum(c["score"] for c in self.criteria), 1)

    @property
    def max_total(self) -> float:
        return float(len(self.criteria))


# ---------------------------------------------------------------------------
# corpus preparation: copy demo, seed defects with known ground truth
# ---------------------------------------------------------------------------


def seed_defects(root: Path) -> list[dict]:
    """Create files with known defects. Returns the ground-truth list."""
    defects: list[dict] = []

    notes = root / "bench-notes"
    notes.mkdir(parents=True, exist_ok=True)

    (notes / "broken-link.md").write_text(
        '---\nid: doc:bench-broken-link\ntitle: "Bench: битая ссылка"\ndoc_type: note\n'
        'lang: ru\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n'
        "# Битая ссылка\n\nСсылка [runbook](does-not-exist.md) не существует.\n", encoding="utf-8")
    defects.append({"path": "bench-notes/broken-link.md", "code": "markdown.link.target_missing"})

    (notes / "unsafe-front-matter.md").write_text(
        "---\nid: doc:bench-unsafe-front-matter\ntitle: Bench: незакавыченное значение\ndoc_type: note\n"
        "lang: ru\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n# H\n", encoding="utf-8")
    defects.append({"path": "bench-notes/unsafe-front-matter.md",
                    "code": "markdown.front_matter.yaml_unsafe"})

    (root / "bench-records").mkdir(parents=True, exist_ok=True)
    (root / "bench-records" / "duplicate-key.json").write_text(
        '{"record_id": "bench:dup", "entity_type": "note", "entity_type": "note"}\n', encoding="utf-8")
    defects.append({"path": "bench-records/duplicate-key.json", "code": "json.duplicate_key"})

    (root / "bench-records" / "invalid-constant.json").write_text("[NaN]\n", encoding="utf-8")
    defects.append({"path": "bench-records/invalid-constant.json", "code": "json.invalid_constant"})

    (root / "bench-records" / "too-deep.json").write_text("[" * 400 + "]" * 400, encoding="utf-8")
    defects.append({"path": "bench-records/too-deep.json", "code": "json.too_deep"})

    (root / "bench-records" / "bad-syntax.json").write_text('{"a": ,}\n', encoding="utf-8")
    defects.append({"path": "bench-records/bad-syntax.json", "code": "json.syntax_error"})

    # decision has a JSON Schema in .todoc/entity_types/decision/, so an out-of-enum
    # status is a real record.schema_violation (workout has no schema at all).
    (root / "bench-records" / "schema-violation.json").write_text(json.dumps({
        "schema_version": 1, "record_id": "decision:bench-1", "entity_type": "decision",
        "title": "Bench: нарушение схемы", "status": "maybe", "decision": "d", "rationale": "r",
        "relations": [{"type_id": "performed_by", "target": {"id": "person:ghost"}}],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    defects.append({"path": "bench-records/schema-violation.json", "code": "record.schema_violation"})
    defects.append({"path": "bench-records/schema-violation.json", "code": "relation.dangling_target"})

    (root / "bench-records" / "relation-unknown-type.json").write_text(json.dumps({
        "schema_version": 1, "record_id": "note:bench-rel", "entity_type": "note",
        "title": "x", "relations": [{"type_id": "loves", "target": {"id": "note:bench-rel"}}],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    defects.append({"path": "bench-records/relation-unknown-type.json", "code": "relation.unknown_type"})

    return defects


# ---------------------------------------------------------------------------
# criterion groups
# ---------------------------------------------------------------------------


def group_contract(rep: Report, root: Path, latency: dict[str, float]) -> None:
    probe = run_todoc(["status", "--root", str(root)], root)
    env = probe.get("envelope") or {}
    expected = ENVELOPE_KEYS | {"guidance"}
    ok = probe["json_ok"] and env.get("schema_version") == 2 and set(env) == expected
    rep.add("K1", "Контракт", "stdout — ровно один JSON-конверт", "pass" if ok else "fail",
            1.0 if ok else 0.0,
            f"exit={probe['exit_code']}, ключи конверта совпадают: {set(env) == expected}",
            {"keys": sorted(env), "stdout_bytes": probe["stdout_bytes"]})

    bad = run_todoc(["docs", "read", "--root", str(root), "--id", "doc:does-not-exist"], root)
    ok = bad["exit_code"] == 3 and not bad["traceback"]
    rep.add("K2", "Контракт", "Стабильные коды выхода (3 = валидация)", "pass" if ok else "fail",
            1.0 if ok else 0.0, f"docs read для неизвестного id → exit {bad['exit_code']}, traceback={bad['traceback']}")

    discovery = run_todoc(["docs", "read", "--root", str(root)], root)
    discovery_data = (discovery.get("envelope") or {}).get("data") or {}
    invalid = run_todoc(["docs", "read", "--root", str(root), "--budget", "0"], root)
    ok = (discovery["exit_code"] == 0 and discovery_data.get("executed") is False
          and invalid["exit_code"] == 2 and invalid["json_ok"])
    rep.add("K3", "Контракт", "Discovery без --id, ошибка при некорректном флаге",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"без --id → exit {discovery['exit_code']}; --budget 0 → exit {invalid['exit_code']}")

    ok_call = run_todoc(["docs", "search", "--root", str(root), "--query", "план", "--limit", "1"], root)
    ok_env = ok_call.get("envelope") or {}
    bad_call = run_todoc(["docs", "read", "--root", str(root), "--id", "doc:does-not-exist"], root)
    bad_env = bad_call.get("envelope") or {}
    val_call = run_todoc(["validate", "--root", str(root), "--all"], root)
    val_env = val_call.get("envelope") or {}
    has_key = all("next_actions" in e for e in (ok_env, bad_env, val_env))
    actionable = bool(ok_env.get("next_actions")) and bool(val_env.get("next_actions") or not val_env.get("diagnostics"))
    ok = ok_call["json_ok"] and bad_call["json_ok"] and has_key and actionable
    rep.add("K4", "Контракт", "next_actions: ключ всегда, подсказка при успехе и при диагностике",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"ключ есть везде: {has_key}; успех→{len(ok_env.get('next_actions') or [])}, "
            f"validate→{len(val_env.get('next_actions') or [])} (диагностик: {len(val_env.get('diagnostics') or [])})",
            {"ok_actions": ok_env.get("next_actions"), "validate_actions": val_env.get("next_actions")})

    guide = run_todoc(["types", "guide", "--root", str(root), "--format", "markdown"], root)
    text = ((guide.get("envelope") or {}).get("data") or {}).get("result", {}).get("guide", "")
    ok = guide["json_ok"] and "dir_type" in text and "entity_type" in text
    rep.add("K5", "Контракт", "Discovery: types guide описывает типовую систему",
            "pass" if ok else "fail", 1.0 if ok else 0.0, f"символов в guide: {len(text)}")


def group_correctness(rep: Report, root: Path, defects: list[dict]) -> None:
    res = run_todoc(["validate", "--root", str(root), "--all"], root)
    diags = (res.get("envelope") or {}).get("diagnostics") or []

    expected = {(d["path"], d["code"]) for d in defects}
    found = {(d["path"], d["code"]) for d in diags}
    bench_found = {x for x in found if x[0].startswith("bench-")}
    true_positives = expected & bench_found
    false_negatives = expected - bench_found
    false_positives = bench_found - expected
    precision = len(true_positives) / len(bench_found) if bench_found else 0.0
    recall = len(true_positives) / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    status = "pass" if f1 >= 0.95 else ("partial" if f1 >= 0.8 else "fail")
    rep.add("K6", "Корректность", "Детекция дефектов: precision/recall на seeded-корпусе",
            status, round(f1, 2),
            f"precision={precision:.2f}, recall={recall:.2f}, F1={f1:.2f}; "
            f"TP={len(true_positives)}, FN={len(false_negatives)}, FP={len(false_positives)}",
            {"expected": sorted(expected), "missed": sorted(false_negatives),
             "unexpected": sorted(false_positives)})

    located = [d for d in diags if d.get("location")]
    with_lines = [d for d in located if d["location"].get("line")]
    share = len(with_lines) / len(diags) if diags else 0.0
    ok = share >= 0.9
    rep.add("K7", "Корректность", "Точные локации (line/column) у диагностик",
            "pass" if ok else "partial", round(share, 2),
            f"{len(with_lines)} из {len(diags)} диагностик имеют номер строки")

    yaml_result = check_front_matter_yaml(root)
    # Критерий, который ничего не измерил, не может считаться пройденным: иначе
    # отсутствие PyYAML выглядит как «90 файлов разобраны без ошибок».
    skipped = yaml_result.get("skipped")
    if skipped:
        rep.add("K8", "Корректность", "Front matter совместим с внешним YAML-парсером",
                "fail", 0.0, f"не измерено: {skipped} (установите extras [dev])", yaml_result)
    else:
        ok = yaml_result["bad"] == 0 and yaml_result["ok"] > 0
        rep.add("K8", "Корректность", "Front matter совместим с внешним YAML-парсером",
                "pass" if ok else "fail", 1.0 if ok else 0.0,
                f"PyYAML: {yaml_result['ok']} файлов разобрано, {yaml_result['bad']} с ошибкой",
                yaml_result)

    explain = run_todoc(["explain-path", "guides/cli-for-agents.md", "--root", str(root)], root)
    data = ((explain.get("envelope") or {}).get("data") or {}).get("result") or {}
    ok = data.get("doc_type") == "guide" and str(data.get("rule_source", "")).startswith("rule:fm-")
    rep.add("K9", "Корректность", "Присвоение doc_type: front matter важнее маски папки",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"doc_type={data.get('doc_type')}, rule_source={data.get('rule_source')}")

    codes = {d["code"] for d in diags}
    # Record writes are validated before the file appears: missing required
    # field, unknown entity type, and duplicate id must all be refused.
    work = root.parent / "records"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(root, work, ignore=shutil.ignore_patterns(".todoc"))
    shutil.copytree(root / ".todoc", work / ".todoc",
                    ignore=shutil.ignore_patterns("index", "cache", "generated"))
    probes: dict[str, tuple[str, dict, int]] = {}
    inputs = root.parent / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    # NOTE: input files stay outside DATA_ROOT: any .json inside the dataset is
    # scanned as a record, so an input file there collides on record_id.
    incomplete = inputs / f"bench-incomplete-{uuid4().hex[:6]}.json"
    incomplete.write_text(json.dumps({"record_id": f"decision:bench-{uuid4().hex[:6]}",
                                      "entity_type": "decision"}), encoding="utf-8")
    res = run_todoc(["records", "create", "--root", str(work), "--type", "decision",
                     "--input-file", str(incomplete), "--apply"], work)
    probes["missing_field"] = (_code_of(res), res, 3)
    unknown = inputs / f"bench-unknown-{uuid4().hex[:6]}.json"
    unknown.write_text(json.dumps({"record_id": "bench:unknown", "entity_type": "nope"}), encoding="utf-8")
    res = run_todoc(["records", "create", "--root", str(work), "--type", "nope",
                     "--input-file", str(unknown), "--apply"], work)
    probes["unknown_type"] = (_code_of(res), res, 3)
    written = not (work / "records" / "decision").exists() or not list((work / "records" / "decision").glob("bench-*"))
    passed = [name for name, (code, res, want) in probes.items()
              if res["exit_code"] == want and code.startswith("record.")]
    ok = len(passed) == len(probes) and written and {"relation.dangling_target", "relation.unknown_type"} <= codes
    rep.add("K10", "Корректность", "Валидация записей: схема, тип, целостность отношений",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"отказы записи: {[(n, probes[n][0]) for n in probes]}; файл не создан: {written}; "
            f"коды отношений: {sorted(c for c in codes if c.startswith('relation.'))}")


def check_front_matter_yaml(root: Path) -> dict:
    """Parse every demo front matter with PyYAML if it is importable."""
    try:
        import yaml  # type: ignore
    except ImportError:
        venv_python = Path(os.environ.get("TODOC_BENCH_VENV", "/tmp/comp")) / "bin" / "python"
        if not venv_python.is_file():
            return {"ok": 0, "bad": 0, "skipped": "PyYAML недоступен"}
        script = """
import json, pathlib, re, sys

import yaml

root = pathlib.Path(sys.argv[1])
ok = bad = 0
errs = []
for p in sorted(root.rglob('*.md')):
    if '.todoc' in p.parts or p.relative_to(root).parts[0].startswith('bench-'):
        continue
    text = p.read_text(encoding='utf-8')
    m = re.match(r'^---\\n(.*?)\\n---\\n', text, re.S)
    if not m:
        continue
    try:
        data = yaml.safe_load(m.group(1))
        assert isinstance(data, dict)
        ok += 1
    except Exception:
        bad += 1
        errs.append(str(p.relative_to(root)))
print(json.dumps({'ok': ok, 'bad': bad, 'files': errs[:5]}))
"""
        proc = subprocess.run([str(venv_python), "-c", script, str(root)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            return {"ok": 0, "bad": 0, "skipped": proc.stderr[:200]}
        return json.loads(proc.stdout.strip().splitlines()[-1])
    ok = bad = 0
    errors: list[str] = []
    for path in markdown_files(root):
        if path.relative_to(root).parts[0].startswith("bench-"):
            continue
        match = re.match(r"^---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
        if not match:
            continue
        try:
            data = yaml.safe_load(match.group(1))
            assert isinstance(data, dict)
            ok += 1
        except Exception:
            bad += 1
            errors.append(str(path.relative_to(root)))
    return {"ok": ok, "bad": bad, "files": errors[:5]}


def group_determinism(rep: Report, root: Path) -> None:
    before = sha256_files(root)
    first = run_todoc(["scan", "--root", str(root)], root)
    second = run_todoc(["scan", "--root", str(root)], root)
    a = json.dumps((first.get("envelope") or {}).get("data"), sort_keys=True)
    b = json.dumps((second.get("envelope") or {}).get("data"), sort_keys=True)
    ok = a == b
    rep.add("K11", "Детерминизм", "Повторный scan даёт идентичные данные",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"совпало: {ok}, размер данных: {len(a)} байт")

    after = sha256_files(root)
    changed = [k for k in before if before[k] != after.get(k)]
    added = [k for k in after if k not in before]
    ok = not changed and not added
    rep.add("K12", "Детерминизм", "Чтение не изменяет источники (инвариантность хешей)",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"изменено: {len(changed)}, добавлено: {len(added)}",
            {"changed": changed[:5], "added": added[:5]})

    v1 = run_todoc(["validate", "--root", str(root), "--all"], root)
    v2 = run_todoc(["validate", "--root", str(root), "--all"], root)
    ids1 = [d["id"] for d in (v1.get("envelope") or {}).get("diagnostics", [])]
    ids2 = [d["id"] for d in (v2.get("envelope") or {}).get("diagnostics", [])]
    same_content = (
        json.dumps([{k: d for k, d in x.items() if k != "id"}
                    for x in (v1.get("envelope") or {}).get("diagnostics", [])], sort_keys=True)
        == json.dumps([{k: d for k, d in x.items() if k != "id"}
                       for x in (v2.get("envelope") or {}).get("diagnostics", [])], sort_keys=True)
    )
    ok = ids1 == ids2
    rep.add("K13", "Детерминизм", "Идентификаторы диагностик стабильны между запусками",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"тела диагностик идентичны: {same_content}; id совпали: {ok}",
            {"ids_run1": ids1[:5], "ids_run2": ids2[:5]})


def group_safety(rep: Report, root: Path) -> None:
    work = root.parent / "safety"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(root, work, ignore=shutil.ignore_patterns(".todoc"))
    shutil.copytree(root / ".todoc", work / ".todoc",
                    ignore=shutil.ignore_patterns("index", "cache", "generated"))

    inputs = root.parent / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    note = inputs / f"bench-input-{uuid4().hex[:8]}.json"  # outside DATA_ROOT
    note.write_text(json.dumps({"schema_version": 1, "record_id": f"note:bench-safety-{uuid4().hex[:8]}",
                                "entity_type": "note", "title": "Bench"}), encoding="utf-8")
    before = sha256_files(work)
    preview = run_todoc(["records", "create", "--root", str(work), "--type", "note",
                         "--input-file", str(note), "--preview"], work)
    after = sha256_files(work)
    plan = ((preview.get("envelope") or {}).get("data") or {}).get("result", {}).get("plan") or {}
    ok = preview["json_ok"] and before == after and plan.get("target_path")
    rep.add("K14", "Безопасность", "preview не пишет файлы и показывает план",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"target={plan.get('target_path')}, файлов изменено: {len([k for k in before if before[k] != after.get(k)])}")

    first = run_todoc(["records", "create", "--root", str(work), "--type", "note",
                       "--input-file", str(note), "--apply"], work)
    second = run_todoc(["records", "create", "--root", str(work), "--type", "note",
                        "--input-file", str(note), "--apply"], work)
    ok = first["exit_code"] == 0 and second["exit_code"] == 5
    rep.add("K15", "Безопасность", "create-only: повторная запись → конфликт (exit 5)",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"первая запись exit={first['exit_code']}, повторная exit={second['exit_code']}")

    outside = root.parent / "escape.md"
    escape = run_todoc(["types", "guide", "--root", str(work), "--out", str(outside)], work)
    escaped = outside.exists()
    outside.unlink(missing_ok=True)
    ok = not escaped
    rep.add("K16", "Безопасность", "Containment: --out не пишет вне DATA_ROOT",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"файл вне корня создан: {escaped}, exit={escape['exit_code']}")


def group_bounded_read(rep: Report, root: Path) -> None:
    full = run_todoc(["docs", "read", "--root", str(root), "--id", "doc:constitution"], root)
    data = ((full.get("envelope") or {}).get("data") or {}).get("result") or {}
    headings = data.get("headings") or []
    ok = bool(headings) and data.get("title")
    rep.add("K17", "Чтение", "Чтение без селектора: заголовок и оглавление",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"заголовков: {len(headings)}, текст: {len(data.get('text', ''))} символов")

    if headings:
        target = next((h for h in headings if h["level"] == 2), headings[0])
        section = run_todoc(["docs", "read", "--root", str(root), "--id", "doc:constitution",
                             "--section", target["title"]], root)
        sdata = ((section.get("envelope") or {}).get("data") or {}).get("result") or {}
        lines = sdata.get("lines") or []
        full_text = (root / "plan" / "constitution.md").read_text(encoding="utf-8")
        ok = (section["json_ok"] and 0 < len(lines) <= 40
              and len("\n".join(lines)) < len(full_text)
              and sdata.get("truncated") is not None)
        rep.add("K18", "Чтение", "Чтение раздела возвращает только раздел (≤40 строк)",
                "pass" if ok else "fail", 1.0 if ok else 0.0,
                f"раздел {target['title'][:30]!r}: {len(lines)} строк")
    else:
        rep.add("K18", "Чтение", "Чтение раздела", "fail", 0.0, "нет заголовков")

    budget = run_todoc(["docs", "read", "--root", str(root), "--id", "doc:constitution",
                        "--budget", "500"], root)
    budget_data = ((budget.get("envelope") or {}).get("data") or {}).get("result") or {}
    content = budget_data.get("text")
    ok = (budget["exit_code"] == 0 and budget["json_ok"] and isinstance(content, str)
          and len(content) == 500 and budget_data.get("truncated") is True)
    rep.add("K19", "Чтение", "--budget ограничивает полезный текст в символах Unicode",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"Текст: {len(content or '')} символов, полный stdout: {budget['stdout_bytes']} байт", budget)

    # JSON Pointer is exercised on a real record document: pick one from disk,
    # address two pointers (a scalar and a nested one) and one missing pointer.
    record_files = [p for p in sorted((root / "records").rglob("*.json"))] if (root / "records").is_dir() else []
    if record_files:
        target = record_files[0]
        doc_id = "doc:" + str(target.relative_to(root))
        expected_id = json.loads(target.read_text(encoding="utf-8")).get("record_id")
        hit = run_todoc(["docs", "read", "--root", str(root), "--id", doc_id, "--pointer", "/record_id"], root)
        value = ((hit.get("envelope") or {}).get("data") or {}).get("result", {}).get("value")
        miss = run_todoc(["docs", "read", "--root", str(root), "--id", doc_id,
                          "--pointer", "/no_such_field"], root)
        ok = hit["json_ok"] and value == expected_id and miss["exit_code"] == 3 and _code_of(miss) == "docs.pointer_not_found"
        detail = f"/record_id → {value!r} (ожидалось {expected_id!r}); /no_such_field → exit {miss['exit_code']}"
    else:
        ok, detail = False, "в датасете нет JSON-записей"
    rep.add("K20", "Чтение", "JSON Pointer (RFC 6901): значение, вложенность, ошибка",
            "pass" if ok else "fail", 1.0 if ok else 0.0, detail)

    csv_read = run_todoc(["docs", "read", "--root", str(root),
                          "--id", "doc:attachments/docs-inventory.csv",
                          "--columns", "doc_id,doc_type", "--rows", "5"], root)
    cdata = ((csv_read.get("envelope") or {}).get("data") or {}).get("result") or {}
    rows = cdata.get("rows") or []
    ok = csv_read["json_ok"] and len(rows) == 5 and set(rows[0]) == {"doc_id", "doc_type"}
    rep.add("K21", "Чтение", "CSV-проекция: колонки и строки",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"строк: {len(rows)}, колонок: {list(rows[0]) if rows else []}")


def labeled_queries(root: Path) -> list[dict]:
    """Build an independent relevance set by scanning files (no todoc involved)."""
    queries = [
        "портабельность", "JSON Pointer", "конституция", "MCP", "эмбеддинги",
        "агрегация единицы", "диагностика", "wikilink", "поколение индекса",
        "token economy", "конкурент", "front matter",
    ]
    docs: list[dict] = []
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        fm = front_matter_of(text)
        docs.append({"id": fm.get("id", f"doc:{path.relative_to(root)}"),
                     "title": fm.get("title", ""), "text": text.lower()})
    labeled = []
    for query in queries:
        terms = [t for t in re.split(r"\s+", query.lower()) if t]
        relevant = {d["id"] for d in docs if any(t in d["text"] for t in terms)}
        labeled.append({"query": query, "relevant": sorted(relevant), "count": len(relevant)})
    return labeled


def group_search(rep: Report, root: Path) -> None:
    labeled = labeled_queries(root)
    recall_at_3: list[float] = []
    precision_at_3: list[float] = []
    reciprocal_ranks: list[float] = []
    per_query = []
    for item in labeled:
        res = run_todoc(["docs", "search", "--root", str(root), "--query", item["query"],
                         "--limit", "3"], root)
        data = (res.get("envelope") or {}).get("data") or {}
        hits = [h["id"] for h in ((data.get("result") or {}).get("items") or [])]
        relevant = set(item["relevant"])
        if not relevant:
            continue
        hit_set = set(hits)
        recall_at_3.append(len(hit_set & relevant) / min(3, len(relevant)))
        precision_at_3.append(len(hit_set & relevant) / len(hits) if hits else 0.0)
        rr = 0.0
        for rank, hid in enumerate(hits, start=1):
            if hid in relevant:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)
        per_query.append({"query": item["query"], "relevant_total": len(relevant),
                          "top3": hits, "relevant_in_top3": len(hit_set & relevant)})

    recall = statistics.mean(recall_at_3) if recall_at_3 else 0.0
    precision = statistics.mean(precision_at_3) if precision_at_3 else 0.0
    mrr = statistics.mean(reciprocal_ranks) if reciprocal_ranks else 0.0
    score = round((recall + mrr) / 2, 2)
    status = "pass" if score >= 0.9 else ("partial" if score >= 0.7 else "fail")
    rep.add("K22", "Поиск", "Recall@3 и MRR на размеченных запросах", status, score,
            f"Recall@3={recall:.2f}, Precision@3={precision:.2f}, MRR={mrr:.2f}, запросов: {len(per_query)}",
            {"per_query": per_query})

    a = run_todoc(["docs", "search", "--root", str(root), "--query", "конституция", "--limit", "5"], root)
    b = run_todoc(["docs", "search", "--root", str(root), "--query", "конституция", "--limit", "5"], root)
    ids_a = [h["id"] for h in ((a.get("envelope") or {}).get("data") or {}).get("result", {}).get("items", [])]
    ids_b = [h["id"] for h in ((b.get("envelope") or {}).get("data") or {}).get("result", {}).get("items", [])]
    ok = ids_a == ids_b and bool(ids_a)
    rep.add("K23", "Поиск", "Ранжирование детерминировано", "pass" if ok else "fail",
            1.0 if ok else 0.0, f"порядок совпал: {ids_a == ids_b}, результатов: {len(ids_a)}")

    page1 = run_todoc(["docs", "search", "--root", str(root), "--query", "план", "--limit", "2"], root)
    cursor = ((page1.get("envelope") or {}).get("data") or {}).get("meta", {}).get("next_cursor")
    page2 = run_todoc(["docs", "search", "--root", str(root), "--query", "план", "--limit", "2",
                       "--cursor", str(cursor)], root)
    d2 = (page2.get("envelope") or {}).get("data") or {}
    ids1 = [h["id"] for h in ((page1.get("envelope") or {}).get("data") or {}).get("result", {}).get("items", [])]
    ids2 = [h["id"] for h in (d2.get("result", {}).get("items") or [])]
    ok = d2.get("meta", {}).get("returned", 0) > 0 and not set(ids1) & set(ids2)
    rep.add("K24", "Поиск", "Пагинация через --cursor продолжает выдачу без повторов",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"cursor={cursor}, вторая страница вернула {d2.get('meta', {}).get('returned')} из total={d2.get('meta', {}).get('total')}, "
            f"пересечений с первой: {len(set(ids1) & set(ids2))}")


def group_robustness(rep: Report, root: Path) -> None:
    work = root.parent / "robust"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(root, work, ignore=shutil.ignore_patterns(".todoc"))
    shutil.copytree(root / ".todoc", work / ".todoc",
                    ignore=shutil.ignore_patterns("index", "cache", "generated"))
    (work / "hostile").mkdir(exist_ok=True)
    (work / "hostile" / "deep.json").write_text("[" * 5000 + "]" * 5000, encoding="utf-8")
    (work / "hostile" / "wide.csv").write_text("a,b\n" + "".join(f"{i},{i}\n" for i in range(20000)), encoding="utf-8")
    (work / "hostile" / "empty.md").write_text("", encoding="utf-8")
    (work / "hostile" / "binary.bin").write_bytes(bytes(range(256)) * 40)

    res = run_todoc(["validate", "--root", str(work), "--all"], work)
    ok = res["json_ok"] and not res["traceback"] and res["exit_code"] in (0, 3)
    rep.add("K25", "Устойчивость", "Враждебный ввод не роняет CLI", "pass" if ok else "fail",
            1.0 if ok else 0.0,
            f"exit={res['exit_code']}, конверт: {res['json_ok']}, traceback: {res['traceback']}")

    bad_cursor = run_todoc(["docs", "search", "--root", str(work), "--query", "x",
                            "--cursor", "abc"], work)
    bad_range = run_todoc(["docs", "read", "--root", str(work), "--id", "doc:home",
                           "--line-range", "abc"], work)
    ok = not bad_cursor["traceback"] and not bad_range["traceback"] and bad_cursor["json_ok"]
    rep.add("K26", "Устойчивость", "Некорректные аргументы → конверт, а не traceback",
            "pass" if ok else "fail", 1.0 if ok else 0.0,
            f"--cursor abc: exit={bad_cursor['exit_code']}, traceback={bad_cursor['traceback']}; "
            f"--line-range abc: exit={bad_range['exit_code']}, traceback={bad_range['traceback']}")


def group_performance(rep: Report, root: Path, latency: dict[str, float], repeats: int) -> None:
    budget_ms = {"status": 1500, "docs search": 2500, "docs read": 2500, "records list": 2500,
                 "validate": 4000, "types list": 1500}
    rows = []
    over = 0
    for name, argv in [("status", ["status"]), ("types list", ["types", "list"]),
                       ("docs search", ["docs", "search", "--query", "план", "--limit", "3"]),
                       ("docs read", ["docs", "read", "--id", "doc:home"]),
                       ("records list", ["records", "list", "--type", "decision", "--limit", "5"]),
                       ("validate", ["validate", "--all"])]:
        times = [run_todoc([*argv, "--root", str(root)], root)["elapsed_s"] * 1000
                 for _ in range(repeats)]
        median = statistics.median(times)
        limit = budget_ms[name]
        p95 = sorted(times)[math.ceil(0.95 * len(times)) - 1]
        rows.append({"command": name, "median_ms": round(median), "p95_ms": round(p95),
                     "limit_ms": limit, "samples_ms": [round(sample) for sample in times],
                     "within": median <= limit})
        if median > limit:
            over += 1
        latency[name] = round(median)
    status = "pass" if over == 0 else ("partial" if over <= 2 else "fail")
    rep.add("K27", "Производительность", "Латентность команд в пределах бюджета",
            status, round(1 - over / len(rows), 2),
            f"команд вне бюджета: {over} из {len(rows)}; медианы: "
            + ", ".join(f"{r['command']}={r['median_ms']}мс" for r in rows),
            rows)


def group_quality(rep: Report, coverage_file: Path, proc: subprocess.CompletedProcess[str]) -> None:
    summary = re.search(r"(\d+) passed", proc.stdout)
    failed = re.search(r"(\d+) failed", proc.stdout)
    ok = proc.returncode == 0 and summary is not None and failed is None
    rep.add("K28", "Качество кода", "Тестовый набор проходит", "pass" if ok else "fail",
            1.0 if ok else 0.0,
            f"{summary.group(0) if summary else 'нет сводки'}"
            + (f", {failed.group(0)}" if failed else ""),
            {"exit_code": proc.returncode,
             "failures": [line for line in proc.stdout.splitlines() if line.startswith("FAILED ")],
             "skips": [line for line in proc.stdout.splitlines() if line.startswith("SKIPPED ")],
             "failure_excerpt": "\n".join(proc.stdout.splitlines()[-24:]) if proc.returncode else ""})

    cov = subprocess.run([sys.executable, "-m", "coverage", "report", f"--data-file={coverage_file}", "--fail-under=100"],
                         cwd=REPO, capture_output=True, text=True)
    total = re.search(r"TOTAL\s+\d+\s+(\d+)\s+\d+\s+(\d+)\s+(\d+)%", cov.stdout)
    if total:
        missed, partial, percent = int(total.group(1)), int(total.group(2)), int(total.group(3))
        ok = cov.returncode == 0 and percent == 100 and missed == 0 and partial == 0
        rep.add("K29", "Качество кода", "Покрытие кода тестами", "pass" if ok else "partial",
                percent / 100, f"покрытие {percent}%, пропущено инструкций: {missed}, веток: {partial}",
                {"exit_code": cov.returncode, "summary": total.group(0)})
    else:
        rep.add("K29", "Качество кода", "Покрытие кода тестами", "partial", 0.5,
                "отчёт покрытия недоступен — запустите coverage run -m pytest")


def _check_git_ignore() -> dict:
    paths = [
        "demo/.todoc/index/CURRENT.json",
        "demo/.todoc/cache/parse/probe.json",
        "demo/.todoc/generated/probe.json",
    ]
    results = {}
    for path in paths:
        proc = subprocess.run(["git", "check-ignore", "--no-index", "-v", path],
                              cwd=REPO, text=True, capture_output=True)
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=REPO, capture_output=True)
        results[path] = {"ignored": proc.returncode == 0, "tracked": tracked.returncode == 0,
                         "pattern": proc.stdout.strip()}
    return {"passed": all(row["ignored"] and not row["tracked"] for row in results.values()), "paths": results}


def _check_git_text_diff(parent: Path) -> dict:
    examples = {
        ".md": ("# Before", "# After"),
        ".json": ('{"status":"before"}', '{"status":"after"}'),
        ".csv": ("status\nbefore", "status\nafter"),
    }
    with TemporaryDirectory(prefix="diff-", dir=parent) as temporary:
        results = {}
        for suffix, (before, after) in examples.items():
            left, right = Path(temporary) / f"before{suffix}", Path(temporary) / f"after{suffix}"
            left.write_text(before + "\n", encoding="utf-8")
            right.write_text(after + "\n", encoding="utf-8")
            proc = subprocess.run(["git", "-c", "core.autocrlf=false", "diff", "--no-index",
                                   "--no-ext-diff", str(left), str(right)],
                                  cwd=REPO, text=True, capture_output=True)
            results[suffix] = proc.returncode == 1 and "@@" in proc.stdout and "Binary files" not in proc.stdout
    return {"passed": all(results.values()), "formats": results}


def _check_offline(root: Path) -> dict:
    unshare = shutil.which("unshare")
    if not unshare:
        return {"status": "not_run", "reason": "unshare is unavailable"}
    prefix = (unshare, "--user", "--map-root-user", "--net", "--")
    probe = subprocess.run([*prefix, "true"], capture_output=True, text=True)
    if probe.returncode != 0:
        return {"status": "not_run", "reason": probe.stderr.strip()}
    commands = [["validate", "--all"], ["docs", "list", "--limit", "1"],
                ["docs", "search", "--query", "план", "--limit", "1"]]
    with TemporaryDirectory(prefix="offline-home-", dir=root.parent) as home:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": home, "XDG_CONFIG_HOME": home,
               "XDG_DATA_HOME": home, "XDG_CACHE_HOME": home, "PYTHONUTF8": "1"}
        evidence = [run_todoc([*cmd, "--root", str(root)], root, prefix=prefix, environment=env)
                    for cmd in commands]
    outcome = "pass" if all(item["json_ok"] and item["exit_code"] == 0 for item in evidence) else "fail"
    return {"status": outcome, "commands": [{"argv": item["argv"], "exit": item["exit_code"]} for item in evidence]}


def group_portability(rep: Report, root: Path) -> None:
    """Measure the eight K30 criteria with separate evidence."""
    source_files = [path for path in root.rglob("*") if path.is_file()
                    and ".todoc" not in path.relative_to(root).parts]
    non_plain = []
    for path in source_files:
        try:
            if "\0" in path.read_text(encoding="utf-8"):
                non_plain.append(path.relative_to(root).as_posix())
        except (UnicodeError, OSError):
            non_plain.append(path.relative_to(root).as_posix())
    databases = sorted(path.relative_to(root).as_posix() for path in root.rglob("*")
                       if path.is_file() and path.suffix.casefold() in (".db", ".sqlite", ".sqlite3"))
    ignores = _check_git_ignore()
    yaml = check_front_matter_yaml(root)
    absolute = []
    for path in markdown_files(root):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if target.startswith("/") or PureWindowsPath(target).is_absolute():
                absolute.append({"path": path.relative_to(root).as_posix(), "target": target})
    git = _check_git_text_diff(root.parent)
    vendor_dirs = sorted(path.relative_to(root).as_posix() for path in root.rglob("*")
                         if path.is_dir() and path.name in (".obsidian", "node_modules"))
    offline = _check_offline(root)
    states = {
        "plain-files": not non_plain, "no-database": not databases,
        "derived-ignored": ignores["passed"], "yaml-front-matter": yaml["bad"] == 0,
        "relative-links": not absolute, "git-diffable": git["passed"], "no-vendor-dirs": not vendor_dirs,
        "offline": None if offline["status"] == "not_run" else offline["status"] == "pass",
    }
    score = sum(value is True for value in states.values())
    rep.add("K30", "Портабельность", "8 подкритериев портабельности (максимум 8)",
            "pass" if score == 8 else "partial", round(score / 8, 2),
            ", ".join(f"{name}={'not_run' if value is None else 'да' if value else 'нет'}"
                      for name, value in states.items()),
            {"results": states, "non_plain": non_plain, "databases": databases, "git_ignore": ignores,
             "yaml": yaml, "absolute_links": absolute, "git_diff": git, "vendor_dirs": vendor_dirs,
             "offline": offline})


# ---------------------------------------------------------------------------
# competitor harnesses
# ---------------------------------------------------------------------------


def competitor_obsidiantools(venv: Path, corpus: Path) -> dict:
    python = venv / "bin" / "python"
    if not python.is_file():
        return {"available": False, "reason": "venv с obsidiantools не найден"}
    # obsidiantools addresses notes by stem, not by path, and get_md_links()
    # needs a note name — so links are resolved against a stem -> path map and
    # absolute URLs are skipped (they are not local targets).
    script = """
import json, sys, time
from pathlib import Path

from obsidiantools.api import Vault

root = Path(sys.argv[1])
started = time.perf_counter()
vault = Vault(root).gather().connect()
elapsed = time.perf_counter() - started
by_stem = {p.stem: p for p in root.rglob('*.md') if '.todoc' not in p.parts}
total = broken = 0
samples = []
for note_key in vault.get_all_file_metadata().index:
    source = by_stem.get(note_key)
    if source is None:
        continue
    for target in vault.get_md_links(note_key):
        if '://' in target:
            continue
        total += 1
        candidate = (source.parent / target.split('#')[0]).resolve()
        if not candidate.exists() and not candidate.with_suffix('.md').exists():
            broken += 1
            if len(samples) < 5:
                samples.append(f"{note_key} -> {target}")
print(json.dumps({
    "elapsed_s": round(elapsed, 3),
    "notes": len(by_stem),
    "local_md_links": total,
    "broken_links_detected": broken,
    "broken_samples": samples,
    "backlinks": len(vault.backlinks_index),
    "isolated_notes": len(vault.isolated_notes),
    "front_matter_index": len(vault.front_matter_index),
}))
"""
    proc = subprocess.run([str(python), "-c", script, str(corpus)], capture_output=True, text=True)
    if proc.returncode != 0:
        return {"available": True, "error": proc.stderr.strip().splitlines()[-1][:200]}
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    data["available"] = True
    # obsidiantools reports unparsable YAML front matter as a warning on either
    # stream; that count is the portability signal (see criterion K8).
    chatter = proc.stderr.splitlines() + proc.stdout.splitlines()
    data["front_matter_warnings"] = len({ln for ln in chatter if "Front matter not populated" in ln})
    return data


def competitor_open_knowledge(venv: Path, corpus: Path) -> dict:
    binary = venv / "bin" / "ok"
    if not binary.is_file():
        return {"available": False, "reason": "venv с open-knowledge не найден"}
    out: dict = {"available": True, "commands": {}}
    version = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=120)
    out["version"] = version.stdout.strip().splitlines()[0] if version.stdout else "?"
    for name, args in [("help", ["--help"]), ("status", ["status", "--cwd", str(corpus)]),
                       ("diagnose", ["diagnose", "--cwd", str(corpus)])]:
        started = time.perf_counter()
        proc = subprocess.run([str(binary), *args], capture_output=True, text=True, timeout=180)
        out["commands"][name] = {"exit_code": proc.returncode,
                                 "elapsed_s": round(time.perf_counter() - started, 3),
                                 "stdout_bytes": len(proc.stdout),
                                 "stderr_bytes": len(proc.stderr),
                                 "first_line": (proc.stdout.strip().splitlines() or [""])[0][:160]}
    out["subcommands"] = _count_subcommands(binary)
    out["writes_into_corpus"] = sorted(
        {p.name for p in corpus.rglob("*") if p.name.startswith(".ok") or p.name == ".ok"})
    return out


def _count_subcommands(binary: Path) -> int:
    """Count top-level subcommands advertised by `ok --help`."""
    proc = subprocess.run([str(binary), "--help"], capture_output=True, text=True, timeout=120)
    text = proc.stdout + proc.stderr
    names = re.findall(r"^\s{2,}([a-z][a-z0-9-]{1,24})\s{2,}", text, re.M)
    return len(set(names))


def competitor_capabilities(venv: Path) -> dict:
    """Which of todoc's capabilities the installed competitors expose at all."""
    binary = venv / "bin" / "ok"
    ok_help = ""
    if binary.is_file():
        proc = subprocess.run([str(binary), "--help"], capture_output=True, text=True, timeout=60)
        ok_help = proc.stdout + proc.stderr
    caps = ["validate", "search", "index", "mcp", "skills", "sync", "ui", "graph", "types", "records"]
    return {cap: (cap in ok_help.lower()) for cap in caps}


# ---------------------------------------------------------------------------
# report rendering
# ---------------------------------------------------------------------------


def render_markdown(rep: Report, meta: dict, competitors: dict) -> str:
    lines = ["# Бенчмарк todoc", "",
             f"Дата: {meta['date']} · датасет: `{meta['corpus']}` · документов: {meta['documents']} · "
             f"записей: {meta['records']}", "",
             f"**Итоговый балл: {rep.total} из {rep.max_total:.0f}** "
             f"({rep.total / rep.max_total * 100:.0f}%)", ""]
    groups: dict[str, list[dict]] = {}
    for criterion in rep.criteria:
        groups.setdefault(criterion["group"], []).append(criterion)
    for group, items in groups.items():
        lines.append(f"## {group}")
        lines.append("")
        lines.append("| ID | Критерий | Статус | Балл | Детали |")
        lines.append("|---|---|---|---|---|")
        for item in items:
            lines.append(f"| {item['id']} | {item['name']} | {item['status']} | {item['score']} | {item['detail']} |")
        lines.append("")
    lines.append("## Конкуренты (установленные)")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(competitors, indent=2, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="меньше повторов латентности")
    parser.add_argument("--venv", default="/tmp/comp", help="venv с конкурентами")
    parser.add_argument("--skip-competitors", action="store_true")
    parser.add_argument("--results-dir", type=Path, default=RESULTS)
    parser.add_argument("--competitors-from", default=None,
                        help="взять блок конкурентов из ранее сохранённого benchmark.json "
                             "(нужно, когда venv с конкурентами недоступен)")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="todoc-bench-") as directory:
        return run_benchmark(args, Path(directory))


def run_benchmark(args: argparse.Namespace, workspace: Path) -> int:
    corpus = workspace / "corpus"
    coverage_file = workspace / "coverage"
    shutil.copytree(DEMO, corpus, ignore=shutil.ignore_patterns(".todoc"))
    shutil.copytree(DEMO / ".todoc", corpus / ".todoc",
                    ignore=shutil.ignore_patterns("index", "cache", "generated"))
    seeded_corpus = workspace / "seeded"
    shutil.copytree(corpus, seeded_corpus)
    defects = seed_defects(seeded_corpus)

    rep = Report()
    latency: dict[str, float] = {}

    test_run = subprocess.run(
        [sys.executable, "-m", "coverage", "run", f"--data-file={coverage_file}",
         "-m", "pytest", "tests", "-o", "addopts=", "-q", "--tb=short", "-r", "fEs", "--no-header"],
        cwd=REPO, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(REPO / "src")},
    )

    group_contract(rep, corpus, latency)
    group_correctness(rep, seeded_corpus, defects)
    group_determinism(rep, seeded_corpus)
    group_safety(rep, corpus)
    group_bounded_read(rep, corpus)
    group_search(rep, corpus)
    group_robustness(rep, corpus)
    group_performance(rep, corpus, latency, repeats=1 if args.quick else 3)
    group_quality(rep, coverage_file, test_run)
    group_portability(rep, corpus)

    competitors: dict = {}
    if args.competitors_from:
        saved = json.loads(Path(args.competitors_from).read_text(encoding="utf-8"))
        competitors = dict(saved.get("competitors") or {})
        for value in competitors.values():
            if isinstance(value, dict):
                value["reused_from"] = str(args.competitors_from)
    if not args.skip_competitors and not args.competitors_from:
        venv = Path(args.venv)
        competitors["obsidiantools"] = competitor_obsidiantools(venv, corpus)
        competitors["open-knowledge"] = competitor_open_knowledge(venv, corpus)
        competitors["open-knowledge-capabilities"] = competitor_capabilities(venv)

    status = run_todoc(["index", "rebuild", "--apply", "--root", str(corpus)], corpus)
    datasets = ((status.get("envelope") or {}).get("data") or {}).get("result", {}).get("datasets") or [{}]
    meta = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "corpus": str(corpus),
            "documents": datasets[0].get("documents"), "records": datasets[0].get("records"),
            "relations": datasets[0].get("relations"), "latency_ms": latency,
            "seeded_defects": len(defects)}

    results = args.results_dir
    results.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "score": {"total": rep.total, "max": rep.max_total},
               "criteria": rep.criteria, "evidence": rep.evidence, "competitors": competitors}
    (results / "benchmark.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    (results / "benchmark.md").write_text(render_markdown(rep, meta, competitors), encoding="utf-8")

    print(f"балл: {rep.total} / {rep.max_total:.0f}")
    for criterion in rep.criteria:
        flag = {"pass": "+", "partial": "~", "fail": "-"}[criterion["status"]]
        print(f"  [{flag}] {criterion['id']} {criterion['name']}: {criterion['detail'][:110]}")
    print(f"результаты: {results / 'benchmark.json'}")
    return 1 if any(c["status"] == "fail" for c in rep.criteria) else 0


if __name__ == "__main__":
    sys.exit(main())
