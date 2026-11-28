"""Portable registry: a single atomic index snapshot + per-doc parse cache (E6)."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from todoc.adapters.formats.markdown import PARSER_VERSION
from todoc.adapters.filesystem.locks import directory_lock
from todoc.adapters.filesystem.scanner import atomic_write, file_hash
from todoc.application.fingerprint import _config_digest, corpus_digest
from todoc.application.storage import SNAPSHOT_SECTIONS, IndexStatus, SnapshotQuery, SnapshotSection
from todoc.errors import IncompleteError



_SHARDS = SNAPSHOT_SECTIONS


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
        except (OSError, ValueError, RecursionError):
            return None
        return data if isinstance(data, dict) else None

    def inspect(self, dataset_id: str, fingerprint: str | None = None) -> IndexStatus:
        """Verify shard bytes without decoding item lists."""
        pointer = self.index_dir / "CURRENT.json"
        try:
            raw = pointer.read_bytes()
        except FileNotFoundError:
            return IndexStatus("missing")
        except OSError:
            return IndexStatus("inaccessible")
        try:
            meta = json.loads(raw)
            if not isinstance(meta, dict) or meta.get("schema_version") != 1:
                return IndexStatus("corrupt")
            if (meta.get("dataset_id") != dataset_id or not isinstance(meta.get("generation_id"), str)
                    or json.loads((self.current_dir / "meta.json").read_bytes()) != meta):
                return IndexStatus("corrupt")
            manifest = meta.get("shards")
            if manifest is None:
                return IndexStatus("stale", meta)
            if not isinstance(manifest, dict) or set(manifest) != set(_SHARDS):
                return IndexStatus("corrupt")
            counts = meta.get("counts")
            if not isinstance(counts, dict) or any(type(counts.get(key)) is not int or counts[key] < 0
                                                  for key in ("documents", "records")):
                return IndexStatus("corrupt")
            if any(file_hash(self.current_dir / f"{key}.json") != manifest[key] for key in _SHARDS):
                return IndexStatus("corrupt")
            if pointer.read_bytes() != raw:
                return IndexStatus("stale")
            if fingerprint is not None and meta.get("corpus_digest") != fingerprint:
                return IndexStatus("stale", meta)
            return IndexStatus("valid", meta)
        except (FileNotFoundError, ValueError, UnicodeError, RecursionError):
            return IndexStatus("corrupt")
        except OSError:
            return IndexStatus("inaccessible")

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
        except (OSError, ValueError, RecursionError):
            return {}
        files = data.get("files") if isinstance(data, dict) else None
        return files if isinstance(files, dict) else {}

    def write_stats(self, files: list[Any]) -> None:
        payload = {"schema_version": 1,
                   "files": {f.rel_path: {"hash": f.hash, "mtime": _mtime_ns(f.abs_path), "size": f.size}
                             for f in files}}
        atomic_write(self.stats_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def load_current(self) -> dict[str, Any] | None:
        return self._read_snapshot(_SHARDS)

    def read_snapshot(self, query: SnapshotQuery) -> dict[str, Any] | None:
        return self._read_snapshot(query.sections, query=query)

    def _read_snapshot(
        self, sections: tuple[SnapshotSection, ...], *, query: SnapshotQuery | None = None,
    ) -> dict[str, Any] | None:
        meta = self.read_current_meta()
        if meta is None:
            return None
        if query is not None and (meta.get("schema_version") != 1 or "shards" not in meta
                                  or meta.get("dataset_id") != query.dataset_id
                                  or meta.get("corpus_digest") != query.fingerprint):
            return None
        gen_id = str(meta.get("generation_id") or "")
        if not self.current_dir.is_dir():
            return None
        payload: dict[str, Any] = {"generation_id": gen_id, "dataset_id": meta.get("dataset_id"),
                                   "corpus_digest": meta.get("corpus_digest"),
                                   "created_at": meta.get("created_at")}
        manifest = meta.get("shards")
        if manifest is not None and (not isinstance(manifest, dict) or set(manifest) != set(_SHARDS)):
            return None
        if query is not None:
            try:
                if json.loads((self.current_dir / "meta.json").read_bytes()) != meta:
                    return None
            except (OSError, ValueError, RecursionError):
                return None
        for name in sections:
            path = self.current_dir / f"{name}.json"
            if not path.is_file():
                return None
            try:
                raw = path.read_bytes()
                if manifest is not None and "sha256:" + hashlib.sha256(raw).hexdigest() != manifest[name]:
                    return None
                payload[name] = json.loads(raw)
            except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
                return None
            if not isinstance(payload[name], list) or any(not isinstance(row, dict) for row in payload[name]):
                return None
        if self.read_current_meta() != meta:
            return None
        return payload

    def publish(self, dataset: dict[str, Any], folders: list[dict[str, Any]], documents: list[dict[str, Any]],
                records: list[dict[str, Any]], relations: list[dict[str, Any]], diagnostics: list[dict[str, Any]],
                digest: str | None = None, mentions: list[dict[str, Any]] | None = None) -> str:
        """Publish a manifest-bound snapshot, restoring the prior directory on a failed swap."""
        gen_id = uuid.uuid4().hex[:12]
        self.index_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "schema_version": 1,
            "dataset_id": dataset["dataset_id"],
            "generation_id": gen_id,
            "config_digest": _config_digest(self.root),
            "corpus_digest": digest,
            "created_at": _utc_now(),
            "shards": {},
            "counts": {"documents": len(documents), "records": len(records)},
        }
        with directory_lock(self.index_dir / ".publish.lock"), tempfile.TemporaryDirectory(
            prefix=".tmp-current-", dir=self.index_dir,
        ) as temp:
            temporary = Path(temp)
            staged = temporary / "staged"
            previous = temporary / "previous"
            staged.mkdir()
            data = (folders, documents, records, relations, diagnostics, mentions or [])
            for name, rows in zip(_SHARDS, data, strict=True):
                raw = (json.dumps(rows, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
                (staged / f"{name}.json").write_bytes(raw)
                meta["shards"][name] = "sha256:" + hashlib.sha256(raw).hexdigest()
            rendered = json.dumps(meta, indent=2, ensure_ascii=False) + "\n"
            (staged / "meta.json").write_text(rendered, encoding="utf-8")
            if self.current_dir.exists():
                self.current_dir.rename(previous)
            moved = False
            try:
                staged.rename(self.current_dir)
                moved = True
                atomic_write(self.index_dir / "CURRENT.json", rendered)
            except BaseException:
                if moved:
                    self.current_dir.rename(staged)
                if previous.exists():
                    previous.rename(self.current_dir)
                raise
        legacy_stage = self.index_dir / ".tmp-current"
        if legacy_stage.is_dir():
            shutil.rmtree(legacy_stage, ignore_errors=True)
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



#: Версия разбора. Поднимается при любом изменении того, как файл превращается в
#: структуру: запись кэша чужой версии — промах, а не источник правды.


def parse_cache_key(path: str) -> str:
    """Имя записи кэша — только от пути.

    Хеш содержимого в имени участвовать не может: тогда запись нельзя было бы найти
    и удалить по пути при записи в файл. Хеш лежит внутри записи и сверяется при
    чтении, так что устаревшая запись даёт промах, а не чужой разбор. Каталог кэша
    и так внутри DATA_ROOT, поэтому `dataset_id` в ключе избыточен.
    """
    return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


def parse_cache_path(root: Path, key: str) -> Path:
    return root / ".todoc" / "cache" / "parse" / f"{key}.json"


def write_parse_cache(root: Path, path: str, content_hash: str, payload: dict[str, Any],
                      parser_version: str = PARSER_VERSION) -> None:
    """Положить разбор файла в кэш. Запись производная: ошибка записи не fatal."""
    envelope = {"path": path, "content_hash": content_hash,
                "parser_version": parser_version, "doc": payload}
    try:
        atomic_write(parse_cache_path(root, parse_cache_key(path)),
                     json.dumps(envelope, indent=2, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_parse_cache(root: Path, path: str, content_hash: str,
                     parser_version: str = PARSER_VERSION) -> dict[str, Any] | None:
    """Разбор файла из кэша либо None.

    Промах — это не только отсутствие записи: несовпавший хеш содержимого, другая
    версия разбора, битый JSON и запись не-словарь дают тот же результат, поэтому
    вызывающий всегда разбирает файл заново и никогда не получает чужой разбор.
    """
    cache_file = parse_cache_path(root, parse_cache_key(path))
    if not cache_file.is_file():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(data, dict):
        return None
    if (data.get("content_hash") != content_hash or data.get("parser_version") != parser_version
            or data.get("path") != path):
        return None
    doc = data.get("doc")
    return doc if isinstance(doc, dict) else None


def invalidate_parse_cache(root: Path, path: str) -> bool:
    """Сбросить кэш парсинга одного файла. True, если запись была.

    Вызывается при записи в файл: кэш обязан сбрасываться вместе с данными, которые
    он описывает. Отсутствие записи — не ошибка (файл могли ещё не разбирать).
    """
    cache_file = parse_cache_path(root, parse_cache_key(path))
    try:
        cache_file.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return True


class JsonParseCache:
    """Dataset-scoped adapter for disposable parsed documents."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def read(self, path: str, content_hash: str) -> dict[str, Any] | None:
        return read_parse_cache(self.root, path, content_hash)

    def write(self, path: str, content_hash: str, payload: dict[str, Any]) -> None:
        write_parse_cache(self.root, path, content_hash, payload)

    def invalidate(self, path: str) -> bool:
        return invalidate_parse_cache(self.root, path)
