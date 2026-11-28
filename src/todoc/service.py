"""Application orchestration shared by CLI commands (thin Click layer calls here)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import scan_dataset
from todoc.application.history import observe_external_changes, open_backend, record_write
from todoc.application.fingerprint import source_fingerprint
from todoc.application.storage import (
    SNAPSHOT_SECTIONS, HistoryStore, IndexStatus, IndexStore, ParseCache, SnapshotQuery, SnapshotSection,
)
from todoc.application import temporal
from todoc.application.validator import build_mentions, stable_id, validate_dataset, validate_relations
from todoc.composition import default_history_store, default_index, default_parse_cache
from todoc.config import load_dataset, load_rules
from todoc.domain.models import Document, Folder
from todoc.errors import IncompleteError, TodocError, ValidationError
from todoc.typing_system.descriptors import TypeRegistry
from todoc.typing_system.resolver import RESERVED_DIR_TYPES, resolve_type


class HistoryRecorder:
    """Пишет событие журнала на каждую запись файла.

    Отдельный объект, а не вызов внутри ``write.py``, чтобы слой записи не знал ни о
    конфигурации, ни о бэкенде: он принимает рекодер и ничего больше. ``None`` вместо
    рекодера означает «история не ведётся» и сохраняет прежнее поведение для тестов.
    """

    def __init__(self, root: Path, backend: Any | None = None, git_head: str | None = None,
                 change_id: str | None = None, store: HistoryStore | None = None) -> None:
        self.root = root
        self.backend = backend
        self.git_head = git_head
        self.change_id = change_id
        self.store = store if store is not None else default_history_store(root)

    def record(self, rel_path: str, before: bytes | None, after: bytes, kind: str, basis: str = "") -> None:
        record_write(self.root, rel_path, before, after, kind=kind, basis=basis,
                     backend=self.backend, git_head=self.git_head, change_id=self.change_id, store=self.store)


class DatasetContext:
    def __init__(self, root: Path, *, index_store: IndexStore | None = None,
                 parse_cache: ParseCache | None = None, history_store: HistoryStore | None = None) -> None:
        self.root = root.resolve()
        self.dataset = load_dataset(self.root)
        self.dataset_id = self.dataset["dataset_id"]
        self.dir_rules, self.doc_rules = load_rules(self.root, self.dataset)
        self.registry_types = TypeRegistry()
        self.registry_types.load(self.root, self.dataset)
        self.registry_types.validate_references(self.dir_rules, self.doc_rules)
        self.store: IndexStore = index_store if index_store is not None else default_index(self.root)
        self.parse_cache: ParseCache = parse_cache if parse_cache is not None else default_parse_cache(self.root)
        self.history_store: HistoryStore = history_store if history_store is not None else default_history_store(self.root)

    def scan_and_validate(self, scanned: tuple[Any, Any] | None = None, *,
                          write_cache: bool = True, check_content: bool = True,
                          verify_sources: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Returns (folders, documents, records, relations, diagnostics) as dicts.

        ``scanned`` lets a caller that already walked the tree (to compute the corpus
        digest) pass the result in instead of paying for a second walk.
        """
        if scanned is None:
            scanned = self.scan()
        scanned_folders, scanned_files = scanned
        diags, doc_info = validate_dataset(self.root, self.dataset, scanned_files, self.dir_rules, self.doc_rules,
                                           registry=self.registry_types, write_cache=write_cache,
                                           parse_cache=self.parse_cache, check_content=check_content,
                                           verify_sources=verify_sources)

        folders: list[dict[str, Any]] = []
        for folder in scanned_folders:
            basename = Path(folder.rel_path).name if folder.rel_path != "." else self.root.name
            dir_type, source, conflicts = resolve_type(
                self.dir_rules, folder.rel_path, basename, None, "dir_type", RESERVED_DIR_TYPES, "unknown"
            )
            for conflict_id in conflicts:
                diags.append({
                    "dataset_id": self.dataset_id, "id": stable_id(folder.rel_path, "config.ambiguous_rule", conflict_id),
                    "code": "config.ambiguous_rule", "severity": "warning", "path": folder.rel_path,
                    "location": {}, "evidence": "", "message": f"Ambiguous rules {conflicts} for {folder.rel_path}.",
                    "suggested_fixes": [],
                })
            folder_id = f"folder:{folder.rel_path}"
            parent = str(Path(folder.rel_path).parent.as_posix()) if folder.rel_path != "." else None
            folders.append(Folder(folder_id, self.dataset_id, folder.rel_path, f"folder:{parent}" if parent and parent != "." else None, dir_type, source).to_dict())

        documents: list[dict[str, Any]] = []
        for scanned in scanned_files:
            info = doc_info.get(scanned.rel_path, {})
            front_matter = info.get("front_matter") or {}
            doc_id = _document_id(scanned.rel_path, front_matter)
            parent = str(Path(scanned.rel_path).parent.as_posix())
            documents.append(Document(
                document_id=doc_id, dataset_id=self.dataset_id, path=scanned.rel_path,
                parent_folder_id=f"folder:{parent}" if parent != "." else "folder:.",
                format=scanned.format, doc_type=str(info.get("doc_type", "unknown")),
                rule_source=str(info.get("rule_source", "default")), hash=scanned.hash, size=scanned.size,
                title=str(info.get("title", "")), status=scanned.status if scanned.status != "ok" else "ok",
            ).to_dict())
            status = front_matter.get("status")
            updated = front_matter.get("updated")
            tags = front_matter.get("tags")
            documents[-1].update(
                attributes=front_matter,
                headings=info.get("headings", []),
                managed_metadata=info.get("managed_metadata", False),
                metadata_pointer=info.get("metadata_pointer", ""),
                lifecycle_status=status if isinstance(status, str) and status.strip() else None,
                updated=updated if isinstance(updated, str) else None,
                tags=[tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else [],
            )
        # Records + relations from JSON files.
        records: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []
        record_texts: dict[str, str] = {}
        for doc in documents:
            parsed = doc_info.get(doc["path"], {}).get("parsed_record")
            if parsed is None:
                continue
            value, text = parsed
            records.append({"record_id": str(value["record_id"]), "entity_type": str(value.get("entity_type", "")),
                            "dataset_id": self.dataset_id, "path": doc["path"], "hash": doc["hash"], "data": value})
            record_texts[doc["path"]] = text
            record_relations = value.get("relations") or []
            if not isinstance(record_relations, list):
                continue
            for relation_index, rel in enumerate(record_relations):
                target = rel.get("target") if isinstance(rel, dict) else None
                if isinstance(target, dict) and target.get("id"):
                    edge = {"type_id": str(rel.get("type_id", "")), "source_id": str(value["record_id"]),
                            "target_id": str(target["id"]), "dataset_id": self.dataset_id,
                            "source_path": doc["path"], "source_pointer": f"/relations/{relation_index}"}
                    # Би-темпоральные поля (§5.5) попадают в ребро, иначе `--as-of`
                    # не смог бы решить, было ли ребро правдой на момент T.
                    edge.update(temporal.temporal_of(rel))
                    relations.append(edge)
        rel_diags = validate_relations(self.dataset_id, records, set(self.registry_types.relation_types),
                                       texts=record_texts)
        diags.extend(d.to_dict() for d in rel_diags)
        diag_dicts = [d.to_dict() if hasattr(d, "to_dict") else d for d in diags]
        return folders, documents, records, relations, diag_dicts

    def build_mentions(self, scanned: tuple[Any, Any], records: list[dict[str, Any]],
                       folders: list[dict[str, Any]], documents: list[dict[str, Any]], *,
                       verify_sources: bool = False
                       ) -> list[dict[str, Any]]:
        """Индекс упоминаний md → цели (план entity-catalog З2). Derived, rebuildable."""
        scanned_folders, scanned_files = scanned
        all_paths = {f.rel_path for f in scanned_files}
        return build_mentions(self.root, scanned_files, records, all_paths, parse_cache=self.parse_cache,
                              verify_sources=verify_sources)

    def history_recorder(self, change_id: str | None = None) -> HistoryRecorder:
        """Рекодер с бэкендом из конфигурации; деградация в embedded видна в `degraded`."""
        backend, degraded = open_backend(self.root, self.dataset)
        recorder = HistoryRecorder(self.root, backend=backend, change_id=change_id, store=self.history_store)
        recorder.degraded = degraded  # type: ignore[attr-defined]
        return recorder

    def observe_history(self, scanned_files: tuple[Any, ...]) -> list[str]:
        """Режим `observed`: расхождение хеша без записи журнала — событие `external.change`.

        Вызывается только там, где скан уже показал расхождение с дайджестом корпуса,
        поэтому команда чтения на неизменном корпусе не пишет в журнал ничего.
        """
        section = self.dataset.get("history")
        mode = "observed"
        if isinstance(section, dict) and isinstance(section.get("mode"), str) and section["mode"]:
            mode = str(section["mode"])
        backend = self.history_recorder().backend
        return observe_external_changes(self.root, [(f.rel_path, f.hash) for f in scanned_files],
                                        backend=backend, mode=mode, store=self.history_store)

    def scan(self, *, strict: bool = False) -> tuple[Any, Any]:
        """Walk the corpus once, reusing cached hashes for files whose mtime+size held."""
        follow = bool(self.dataset.get("follow_symlinks", False))
        max_bytes = int((self.dataset.get("limits") or {}).get("max_file_bytes", 10485760))
        return scan_dataset(self.root, follow_symlinks=follow, max_file_bytes=max_bytes,
                            hash_cache=None if strict else self.store.read_stats(), strict=strict)

    def index_status(self) -> IndexStatus:
        return self.store.inspect(self.dataset_id)

    def load_published_index(self) -> dict[str, Any] | None:
        return self.store.load_current()

    def read_index(
        self, *, include_mentions: bool = True, sections: tuple[SnapshotSection, ...] | None = None,
    ) -> dict[str, Any]:
        """Read a verified projection or assemble one in memory without publishing."""
        requested = SNAPSHOT_SECTIONS if sections is None else tuple(dict.fromkeys(("documents", "diagnostics", *sections)))
        read_mentions = include_mentions and "mentions" in requested

        try:
            scanned = self.scan(strict=True)
            digest = source_fingerprint(self.root, *scanned)
            current = self.store.read_snapshot(SnapshotQuery(self.dataset_id, digest, requested))
            manifest = {file.rel_path: file.hash for file in scanned[1]}
            if (current is not None
                    and {doc.get("path"): doc.get("hash") for doc in current["documents"]} == manifest
                    and all({"document_id", "path", "hash", "format", "title", "status", "doc_type"} <= doc.keys()
                            and isinstance(doc.get("attributes"), dict) and isinstance(doc.get("headings"), list)
                            and "managed_metadata" in doc
                            for doc in current["documents"])
                    and all("source_path" in edge for edge in current.get("relations", []))):
                payload = current
            else:
                folders, documents, records, relations, diagnostics = self.scan_and_validate(
                    scanned, write_cache=False, check_content=read_mentions, verify_sources=True
                )
                payload = {
                    "folders": folders, "documents": documents, "records": records,
                    "relations": relations, "diagnostics": diagnostics,
                    "mentions": self.build_mentions(scanned, records, folders, documents, verify_sources=True)
                    if read_mentions else [],
                }
                payload = {name: payload[name] for name in requested}
            if source_fingerprint(self.root, *self.scan(strict=True)) != digest:
                raise IncompleteError("Dataset changed while reading.")
        except OSError as exc:
            raise IncompleteError(f"Dataset could not be read: {exc.strerror or type(exc).__name__}") from exc
        return {**payload, "dataset_id": self.dataset_id, "corpus_digest": digest}

    def _publish_index(self, scanned: tuple[Any, Any], digest: str, *, observe: bool) -> tuple[str, tuple[list[dict[str, Any]], ...]]:
        try:
            collections = self.scan_and_validate(scanned, verify_sources=True)
            folders, documents, records, relations, diagnostics = collections
            mentions = self.build_mentions(scanned, records, folders, documents, verify_sources=True)
            if source_fingerprint(self.root, *self.scan(strict=True)) != digest:
                raise IncompleteError("Dataset changed during index construction. Retry the rebuild.", "read.changed")
            generation = self.store.publish(self.dataset, folders, documents, records, relations,
                                            diagnostics, digest, mentions=mentions)
        except OSError as exc:
            raise IncompleteError(f"Could not publish the index: {exc}", "index.publish_failed") from exc
        try:
            self.store.write_stats(scanned[1])
        except (OSError, TodocError) as exc:
            raise IncompleteError(f"Index {generation} was published, but scan statistics were not saved: {exc}",
                                  "index.stats_failed") from exc
        if observe:
            try:
                self.observe_history(scanned[1])
            except (OSError, TodocError) as exc:
                raise IncompleteError(f"Index {generation} was published. History observation failed: {exc}",
                                      "index.history_failed") from exc
        return generation, collections

    def rebuild_index(self, force: bool = True, observe: bool = True) -> dict[str, Any]:
        """Recompute and publish the snapshot. ``force=False`` reuses a valid one."""
        scanned = self.scan(strict=True)
        digest = source_fingerprint(self.root, *scanned)
        if not force:
            meta = self.store.read_current_meta()
            if meta and meta.get("corpus_digest") == digest:
                existing = self.store.load_current()
                if existing is not None and existing.get("dataset_id") == self.dataset_id:
                    return {"dataset_id": self.dataset_id, "generation_id": existing.get("generation_id"),
                            "corpus_digest": digest, "reused": True,
                            "folders": len(existing.get("folders") or []),
                            "documents": len(existing.get("documents") or []),
                            "records": len(existing.get("records") or []),
                            "relations": len(existing.get("relations") or []),
                            "diagnostics": len(existing.get("diagnostics") or [])}
        gen_id, (folders, documents, records, relations, diagnostics) = self._publish_index(
            scanned, digest, observe=observe,
        )
        return {"dataset_id": self.dataset_id, "generation_id": gen_id, "corpus_digest": digest,
                "reused": False, "folders": len(folders), "documents": len(documents),
                "records": len(records), "relations": len(relations), "diagnostics": len(diagnostics)}

    def ensure_index(self) -> dict[str, Any]:
        """The single invalidation point: reuse the snapshot unless the corpus moved.

        Read commands call this, not ``rebuild_index``. A command that only reads must
        not publish, otherwise an unchanged corpus accumulates one snapshot per run.
        """
        scanned = self.scan(strict=True)
        digest = source_fingerprint(self.root, *scanned)
        meta = self.store.read_current_meta()
        if meta and meta.get("corpus_digest") == digest:
            payload = self.store.load_current()
            if payload is not None and payload.get("dataset_id") == self.dataset_id:
                return payload
        self._publish_index(scanned, digest, observe=True)
        payload = self.store.load_current()
        if payload is None:
            raise IncompleteError("Index publish produced no readable snapshot. Run `todoc index rebuild`.")
        return payload


def _document_id(rel_path: str, front_matter: dict[str, Any]) -> str:
    if isinstance(front_matter, dict) and front_matter.get("id"):
        return str(front_matter["id"])
    return f"doc:{rel_path}"


def resolve_roots(roots: tuple[str, ...]) -> list[Path]:
    if roots:
        return [Path(r) for r in roots]
    import os
    env = os.environ.get("TODOC_ROOT")
    if env:
        return [Path(p) for p in env.split(os.pathsep) if p]
    raise ValidationError("No --root given and TODOC_ROOT is not set", "usage.missing_root")
