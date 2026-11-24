"""Shared fixtures: initialized dataset + sample files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from todoc.config import init_dataset


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    data_root = tmp_path / "knowledge"
    data_root.mkdir()
    init_dataset(data_root)
    return data_root


@pytest.fixture()
def sample_md(root: Path) -> Path:
    path = root / "notes" / "design.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntitle: Design\n---\n\n# Design\n\n## Decision\n\nWe use refresh token rotation.\n\n## Alternatives\n\nSee [runbook](../ops/runbook.md).\n",
        encoding="utf-8",
    )
    ops = root / "ops" / "runbook.md"
    ops.parent.mkdir(parents=True, exist_ok=True)
    ops.write_text("# Runbook\n\nSteps.\n", encoding="utf-8")
    return path


@pytest.fixture()
def sample_csv(root: Path) -> Path:
    path = root / "data" / "runs.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("run_id,status\nr1,ok\nr2,fail\n", encoding="utf-8")
    return path


@pytest.fixture()
def sample_record(root: Path) -> Path:
    path = root / "records" / "workouts" / "w1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 1, "record_id": "workout:2026-11-24-sergei-01", "entity_type": "workout",
        "date": "2026-11-24", "volume": {"value": 100, "unit": "kg"},
        "relations": [{"type_id": "performed_by", "target": {"kind": "record", "id": "person:sergei"}}],
    }, indent=2) + "\n", encoding="utf-8")
    person = root / "records" / "persons" / "p1.json"
    person.parent.mkdir(parents=True, exist_ok=True)
    person.write_text(json.dumps({"schema_version": 1, "record_id": "person:sergei", "entity_type": "person", "name": "Sergei"}) + "\n", encoding="utf-8")
    return path
