"""Portable registry: a single atomic index snapshot + per-doc parse cache (E6)."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
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


def corpus_digest(files: list[Any], config_digest: str) -> str:
    """SHA-256 over sorted (rel_path, content_hash) pairs plus the config digest.

    Two scans of an unchanged corpus produce the same digest, which is what lets a
    read command reuse the published index instead of republishing it. ``created_at``
    is deliberately not an input: metadata must not invalidate the index.
    """
    h = hashlib.sha256()
    for path, digest in sorted((f.rel_path, f.hash) for f in files):
        h.update(path.encode("utf-8"))
        h.update(b"\0")
        h.update(digest.encode("utf-8"))
        h.update(b"\n")
    h.update(config_digest.encode("utf-8"))
    return "sha256:" + h.hexdigest()


class RegistryStore:
    """File-backed index under .todoc/index/ (derived, rebuildable).

    A single snapshot lives in ``current/`` and is overwritten in place. Earlier
    revisions published one directory per run, so the index grew without bound on
    an unchanged corpus; the journal (not the index) is where history belongs.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.index_dir = root / ".todoc" / "index"
        self.current_dir = self.index_dir / "current"
        self.stats_path = self.index_dir / "stats.json"
        #: Legacy layout, removed on the next publish. Kept as an attribute so the
        #: migration is visible rather than silent.
        self.legacy_generations_dir = self.index_dir / "generations"

    def config_digest(self) -> str:
        return _config_digest(self.root)

    def read_current_meta(self) -> dict[str, Any] | None:
        current = self.index_dir / "CURRENT.json"
        if not current.is_file():
            return None
        try:
            data = json.loads(current.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def current_generation_id(self) -> str | None:
        meta = self.read_current_meta()
        if meta is None:
            return None
        gen = meta.get("generation_id")
        return str(gen) if gen else None

    def read_stats(self) -> dict[str, dict[str, Any]]:
        """path -> {hash, mtime, size}; lets a rescan skip re-reading unchanged files."""
        if not self.stats_path.is_file():
            return {}
        try:
            data = json.loads(self.stats_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        files = data.get("files") if isinstance(data, dict) else None
        return files if isinstance(files, dict) else {}

    def write_stats(self, files: list[Any]) -> None:
        payload = {"schema_version": 1,
                   "files": {f.rel_path: {"hash": f.hash, "mtime": _mtime_ns(f.abs_path), "size": f.size}
                             for f in files}}
        atomic_write(self.stats_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def load_current(self) -> dict[str, Any] | None:
        meta = self.read_current_meta()
        if meta is None:
            return None
        gen_id = str(meta.get("generation_id") or "")
        if not self.current_dir.is_dir():
            return None
        payload: dict[str, Any] = {"generation_id": gen_id,
                                   "corpus_digest": meta.get("corpus_digest"),
                                   "created_at": meta.get("created_at")}
        for name in ("folders", "documents", "records", "relations", "diagnostics"):
            path = self.current_dir / f"{name}.json"
            if not path.is_file():
                return None
            try:
                payload[name] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return payload

    def publish(self, dataset: dict[str, Any], folders: list[dict[str, Any]], documents: list[dict[str, Any]],
                records: list[dict[str, Any]], relations: list[dict[str, Any]], diagnostics: list[dict[str, Any]],
                digest: str | None = None) -> str:
        """Atomically (re)publish the single snapshot. On error, the old one stays."""
        gen_id = uuid.uuid4().hex[:12]
        tmp_dir = self.index_dir / ".tmp-current"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "schema_version": 1,
            "dataset_id": dataset["dataset_id"],
            "generation_id": gen_id,
            "config_digest": _config_digest(self.root),
            "corpus_digest": digest,
            "created_at": _utc_now(),
        }
        try:
            for name, payload in (("folders", folders), ("documents", documents), ("records", records),
                                  ("relations", relations), ("diagnostics", diagnostics)):
                (tmp_dir / f"{name}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            (tmp_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            # Validate: all JSON parse + meta present.
            for name in ("folders", "documents", "records", "relations", "diagnostics", "meta"):
                json.loads((tmp_dir / f"{name}.json").read_text(encoding="utf-8"))
            if self.current_dir.exists():
                shutil.rmtree(self.current_dir)
            tmp_dir.rename(self.current_dir)
        except BaseException:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
        atomic_write(self.index_dir / "CURRENT.json", json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
        # Migration: the pre-redesign layout accumulated one directory per run.
        if self.legacy_generations_dir.is_dir():
            shutil.rmtree(self.legacy_generations_dir, ignore_errors=True)
        return gen_id

    def require_current(self) -> dict[str, Any]:
        payload = self.load_current()
        if payload is None:
            raise IncompleteError("No complete index generation. Run `todoc index rebuild`.")
        return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0



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
