"""CLI-контракт Фаз 0 и 4: stale, index rebuild --force, сквозные K47/K48."""

import json
import os
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

from todoc.cli import cli
from todoc.errors import TodocError

BENCH = {"meta": {"date": "2026-11-25", "score": 29.5}, "probes": {"S1": "ok"}}


def _run(runner, args):
    result = runner.invoke(cli, args)
    if isinstance(result.exception, TodocError):
        result.exit_code = result.exception.exit_code
    return result


def _json(result):
    return json.loads(result.output)


def _run_cli(root, args):
    """Настоящий CLI в подпроцессе: только так исполняется конверт ошибки из main()."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    return subprocess.run([sys.executable, "-m", "todoc", "--root", str(root), *args],
                          capture_output=True, text=True, env=env, timeout=120)


def _seed(root):
    """Корпус с одной зависимостью, заякоренной на текущее значение."""
    import subprocess
    import sys
    from pathlib import Path

    from todoc.application.staleness import format_anchor, fragment_hash

    bench = Path(root) / "bench" / "results"
    bench.mkdir(parents=True, exist_ok=True)
    (bench / "benchmark.json").write_text(json.dumps(BENCH, indent=2) + "\n", encoding="utf-8")
    state = Path(root) / "docs" / "state"
    state.mkdir(parents=True, exist_ok=True)
    dep = {"path": "bench/results/benchmark.json", "pointer": "/meta/date"}
    anchor = format_anchor({**dep, "hash": fragment_hash(Path(root), dep)[0]})
    (state / "10-testing.md").write_text(
        f'---\ntitle: "Качество"\ndoc_type: note\nderived_from: ["{anchor}"]\n---\n\n# Качество\n',
        encoding="utf-8")
    return {"bench": bench / "benchmark.json", "doc": state / "10-testing.md", "anchor": anchor}


def _set_date(path, value):
    data = json.loads(path.read_text(encoding="utf-8"))
    data["meta"]["date"] = value
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# --- Фаза 0 ------------------------------------------------------------------


def test_index_status_reports_digest_and_created_at(root):
    runner = CliRunner()
    _run(runner, ["--root", str(root), "index", "rebuild", "--apply"])
    data = _json(_run(runner, ["--root", str(root), "index", "status"]))["data"]["result"]["datasets"][0]
    assert data["current"] is True
    assert str(data["corpus_digest"]).startswith("sha256:")
    assert str(data["created_at"]).endswith("Z")


def test_index_rebuild_reuses_unless_forced(root, sample_md):
    """K31 на уровне CLI: повторный rebuild без --force не издаёт новый снимок."""
    runner = CliRunner()
    first = _json(_run(runner, ["--root", str(root), "index", "rebuild", "--apply"]))["data"]["result"]["datasets"][0]
    assert first["reused"] is False
    soft = _json(_run(runner, ["--root", str(root), "index", "rebuild", "--apply"]))["data"]["result"]["datasets"][0]
    assert soft["reused"] is True and soft["generation_id"] == first["generation_id"]
    hard = _json(_run(runner, ["--root", str(root), "index", "rebuild", "--apply", "--force"]))["data"]["result"]["datasets"][0]
    assert hard["reused"] is False and hard["generation_id"] != first["generation_id"]


def test_read_command_does_not_republish(root, sample_md):
    """K31: команда чтения на неизменном корпусе не меняет снимок."""
    runner = CliRunner()
    _run(runner, ["--root", str(root), "index", "rebuild", "--apply"])
    before = _json(_run(runner, ["--root", str(root), "index", "status"]))["data"]["result"]["datasets"][0]["generation_id"]
    for _ in range(3):
        assert _run(runner, ["--root", str(root), "docs", "search", "--query", "design"]).exit_code == 0
    after = _json(_run(runner, ["--root", str(root), "index", "status"]))["data"]["result"]["datasets"][0]["generation_id"]
    assert before == after


def test_single_snapshot_on_disk(root, sample_md):
    """K32: в .todoc/index ровно один снимок, и размер не растёт от числа запусков."""
    runner = CliRunner()
    for _ in range(3):
        _run(runner, ["--root", str(root), "index", "rebuild", "--apply"])
    index_dir = root / ".todoc" / "index"
    assert (index_dir / "current").is_dir()
    assert not (index_dir / "generations").exists()
    assert sorted(p.name for p in index_dir.iterdir()) == ["CURRENT.json", "current", "stats.json"]


# --- Фаза 4 ------------------------------------------------------------------


def test_stale_clean_corpus(root):
    runner = CliRunner()
    _seed(root)
    data = _json(_run(runner, ["--root", str(root), "stale"]))
    assert data["ok"] is True and data["data"]["result"]["stale"] == 0


def test_stale_reports_drift(root):
    """K33 через CLI."""
    runner = CliRunner()
    seeded = _seed(root)
    _set_date(seeded["bench"], "2026-11-26")
    envelope = _json(_run(runner, ["--root", str(root), "stale"]))
    assert envelope["data"]["result"]["stale"] == 1
    assert envelope["diagnostics"][0]["code"] == "staleness.dependency_changed"


def test_stale_ignores_unrelated_change(root):
    """K44 через CLI."""
    runner = CliRunner()
    seeded = _seed(root)
    data = json.loads(seeded["bench"].read_text(encoding="utf-8"))
    data["probes"]["S1"] = "совсем другое"
    seeded["bench"].write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    assert _json(_run(runner, ["--root", str(root), "stale"]))["data"]["result"]["stale"] == 0


def test_stale_path_filter(root):
    runner = CliRunner()
    seeded = _seed(root)
    _set_date(seeded["bench"], "2026-11-26")
    assert _json(_run(runner, ["--root", str(root), "stale", "--path",
                               "docs/state/10-testing.md"]))["data"]["result"]["stale"] == 1
    assert _json(_run(runner, ["--root", str(root), "stale", "--path", "нет.md"]))["data"]["result"]["stale"] == 0


def test_stale_ack_preview_then_apply(root):
    """K45 через CLI + review-first: без --apply ничего не пишется."""
    runner = CliRunner()
    seeded = _seed(root)
    _set_date(seeded["bench"], "2026-11-26")
    before = seeded["doc"].read_text(encoding="utf-8")

    preview = _json(_run(runner, ["--root", str(root), "stale", "--ack", "docs/state/10-testing.md",
                                  "--reason", "дату обновил вручную"]))
    assert preview["data"]["result"]["applied"] is False
    assert seeded["doc"].read_text(encoding="utf-8") == before
    assert _json(_run(runner, ["--root", str(root), "stale"]))["data"]["result"]["stale"] == 1

    applied = _json(_run(runner, ["--root", str(root), "stale", "--ack", "docs/state/10-testing.md",
                                  "--reason", "дату обновил вручную", "--apply"]))
    assert applied["data"]["result"]["applied"] is True
    assert _json(_run(runner, ["--root", str(root), "stale"]))["data"]["result"]["stale"] == 0

    _set_date(seeded["bench"], "2026-11-27")
    assert _json(_run(runner, ["--root", str(root), "stale"]))["data"]["result"]["stale"] == 1


def test_stale_ack_requires_reason(root):
    """--ack без --reason — ошибка использования (exit 2)."""
    runner = CliRunner()
    _seed(root)
    result = runner.invoke(cli, ["--root", str(root), "stale", "--ack", "docs/state/10-testing.md"])
    assert isinstance(result.exception, TodocError)
    assert result.exception.exit_code == 2
    assert result.exception.code == "usage.error"


def test_stale_ack_unknown_path(root):
    runner = CliRunner()
    _seed(root)
    try:
        result = runner.invoke(cli, ["--root", str(root), "stale", "--ack", "нет.md", "--reason", "x"])
        raise_result = result.exception
    except TodocError as exc:
        raise_result = exc
    assert isinstance(raise_result, TodocError)
    assert raise_result.code == "staleness.owner_not_found"


# --- сквозные K47, K48 -------------------------------------------------------


def test_new_commands_never_prompt_under_no_input(root):
    """K47: --no-input не требует TTY."""
    runner = CliRunner()
    _seed(root)
    for args in (["stale"], ["index", "status"], ["index", "rebuild", "--apply", "--force"]):
        result = _run(runner, ["--root", str(root), "--no-input", *args])
        assert result.exit_code == 0, args


def test_stale_returns_envelope_on_error(root):
    """K48: даже при ошибке в stdout ровно один JSON-конверт с ok:false и nonzero exit."""
    _seed(root)
    proc = _run_cli(root, ["stale", "--ack", "docs/state/10-testing.md"])
    assert proc.returncode == 2, proc.stderr
    envelope = json.loads(proc.stdout)
    assert envelope["ok"] is False
    assert envelope["diagnostics"][0]["code"] == "usage.error"
    assert envelope["next_actions"]


def test_stale_operation_error_envelope(root):
    """K48 для операционной ошибки: exit 1, тот же конверт."""
    _seed(root)
    proc = _run_cli(root, ["stale", "--ack", "нет.md", "--reason", "x"])
    assert proc.returncode == 1, proc.stderr
    envelope = json.loads(proc.stdout)
    assert envelope["ok"] is False
    assert envelope["diagnostics"][0]["code"] == "staleness.owner_not_found"


def test_stale_severity_filter(root):
    runner = CliRunner()
    seeded = _seed(root)
    _set_date(seeded["bench"], "2026-11-26")
    assert _json(_run(runner, ["--root", str(root), "stale", "--severity", "warning"]))["data"]["result"]["stale"] == 1
    assert _json(_run(runner, ["--root", str(root), "stale", "--severity", "error"]))["data"]["result"]["stale"] == 0


def test_stale_ack_on_record_refused(root):
    """Подтверждение пишется только в markdown front matter."""
    runner = CliRunner()
    records = root / "records" / "task"
    records.mkdir(parents=True)
    (records / "t1.json").write_text(json.dumps({
        "record_id": "task:t1", "entity_type": "task",
        "derived_from": [{"path": "a.json", "pointer": "/v", "hash": "sha256:aa"}],
    }) + "\n", encoding="utf-8")
    (root / "a.json").write_text(json.dumps({"v": 1}) + "\n", encoding="utf-8")
    try:
        result = runner.invoke(cli, ["--root", str(root), "stale", "--ack", "records/task/t1.json",
                                     "--reason", "x"])
        exc = result.exception
    except TodocError as e:
        exc = e
    assert isinstance(exc, TodocError) and exc.code == "staleness.ack_unsupported"


def test_stale_ack_without_resolvable_dependency(root):
    runner = CliRunner()
    doc = root / "dangling.md"
    doc.write_text('---\ntitle: "Б"\nderived_from: ["нет.json@sha256:aa"]\n---\n\nтело\n', encoding="utf-8")
    try:
        result = runner.invoke(cli, ["--root", str(root), "stale", "--ack", "dangling.md", "--reason", "x"])
        exc = result.exception
    except TodocError as e:
        exc = e
    assert isinstance(exc, TodocError) and exc.code == "staleness.ack_unsupported"


def test_stale_ack_expected_hash_mismatch(root):
    """expected_hash защищает от записи поверх чужой правки (exit 5)."""
    runner = CliRunner()
    seeded = _seed(root)
    _set_date(seeded["bench"], "2026-11-26")
    try:
        result = runner.invoke(cli, ["--root", str(root), "stale", "--ack", "docs/state/10-testing.md",
                                     "--reason", "x", "--apply", "--expected-hash", "sha256:неверный"])
        exc = result.exception
    except TodocError as e:
        exc = e
    assert isinstance(exc, TodocError) and exc.code == "write.hash_mismatch"


def test_stale_ack_expected_hash_match(root):
    runner = CliRunner()
    seeded = _seed(root)
    _set_date(seeded["bench"], "2026-11-26")
    from todoc.adapters.filesystem.scanner import file_hash
    actual = file_hash(seeded["doc"])
    envelope = _json(_run(runner, ["--root", str(root), "stale", "--ack", "docs/state/10-testing.md",
                                   "--reason", "x", "--apply", "--expected-hash", actual]))
    assert envelope["data"]["result"]["applied"] is True
