"""Portable registry: atomic generations + per-doc parse cache (E6)."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import atomic_write
from todoc.errors import IncompleteError


def _config_digest(root: Path) -> str:
    h = hashlib.sha256()
    todoc_dir = root / ".todoc"
    if todoc_dir.is_dir():
        for path in sorted(todoc_dir.rglob("*.json")):
            if "index" in path.parts or "cache" in path.parts or "generated" in path.parts:
                continue
            try:
                h.update(path.read_bytes())
            except OSError:
                continue
    return "sha256:" + h.hexdigest()


class RegistryStore:
    """File-backed generations under .todoc/index/ (derived, rebuildable)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.index_dir = root / ".todoc" / "index"
        self.generations_dir = self.index_dir / "generations"

    def current_generation_id(self) -> str | None:
        current = self.index_dir / "CURRENT.json"
        if not current.is_file():
            return None
        try:
            data = json.loads(current.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        gen = data.get("generation_id")
        return str(gen) if gen else None

    def load_current(self) -> dict[str, Any] | None:
        gen_id = self.current_generation_id()
        if gen_id is None:
            return None
        gen_dir = self.generations_dir / gen_id
        if not gen_dir.is_dir():
            return None
        payload: dict[str, Any] = {"generation_id": gen_id}
        for name in ("folders", "documents", "records", "relations", "diagnostics"):
            path = gen_dir / f"{name}.json"
            if not path.is_file():
                return None
            try:
                payload[name] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return payload

    def publish(self, dataset: dict[str, Any], folders: list[dict[str, Any]], documents: list[dict[str, Any]],
                records: list[dict[str, Any]], relations: list[dict[str, Any]], diagnostics: list[dict[str, Any]]) -> str:
        """Atomically publish a new generation. On error, old CURRENT stays."""
        gen_id = uuid.uuid4().hex[:12]
        gen_dir = self.generations_dir / gen_id
        tmp_dir = self.generations_dir / f".tmp-{gen_id}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "schema_version": 1,
            "dataset_id": dataset["dataset_id"],
            "generation_id": gen_id,
            "config_digest": _config_digest(self.root),
        }
        try:
            for name, payload in (("folders", folders), ("documents", documents), ("records", records),
                                  ("relations", relations), ("diagnostics", diagnostics)):
                (tmp_dir / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (tmp_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            # Validate: all JSON parse + meta present.
            for name in ("folders", "documents", "records", "relations", "diagnostics", "meta"):
                json.loads((tmp_dir / f"{name}.json").read_text(encoding="utf-8"))
            if gen_dir.exists():
                shutil.rmtree(gen_dir)
            tmp_dir.rename(gen_dir)
        except BaseException:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
        atomic_write(self.index_dir / "CURRENT.json", json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
        return gen_id

    def require_current(self) -> dict[str, Any]:
        payload = self.load_current()
        if payload is None:
            raise IncompleteError("No complete index generation. Run `todoc index rebuild`.")
        return payload


def parse_cache_key(dataset_id: str, path: str, content_hash: str, parser_version: str) -> str:
    raw = f"{dataset_id}|{path}|{content_hash}|{parser_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def write_parse_cache(root: Path, key: str, payload: dict[str, Any]) -> None:
    cache_dir = root / ".todoc" / "cache" / "parse"
    atomic_write(cache_dir / f"{key}.json", json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def read_parse_cache(root: Path, key: str) -> dict[str, Any] | None:
    path = root / ".todoc" / "cache" / "parse" / f"{key}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
