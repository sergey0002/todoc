"""Application orchestration shared by CLI commands (thin Click layer calls here)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import scan_dataset
from todoc.adapters.formats.jsonfmt import parse_json
from todoc.application.history import observe_external_changes, open_backend, record_write
from todoc.application.registry import RegistryStore, corpus_digest
from todoc.application import temporal
from todoc.application.validator import build_mentions, stable_id, validate_dataset, validate_relations
from todoc.config import load_dataset, load_rules
from todoc.domain.models import Document, Folder
from todoc.errors import IncompleteError, ValidationError
from todoc.typing_system.descriptors import TypeRegistry
from todoc.typing_system.resolver import RESERVED_DIR_TYPES, resolve_type


class HistoryRecorder:
    """Пишет событие журнала на каждую запись файла.

    Отдельный объект, а не вызов внутри ``write.py``, чтобы слой записи не знал ни о
    конфигурации, ни о бэкенде: он принимает рекодер и ничего больше. ``None`` вместо
    рекодера означает «история не ведётся» и сохраняет прежнее поведение для тестов.
    """

    def __init__(self, root: Path, backend: Any | None = None, git_head: str | None = None,
                 change_id: str | None = None) -> None:
        self.root = root
        self.backend = backend
        self.git_head = git_head
        self.change_id = change_id

    def record(self, rel_path: str, before: bytes | None, after: bytes, kind: str, basis: str = "") -> None:
        record_write(self.root, rel_path, before, after, kind=kind, basis=basis,
                     backend=self.backend, git_head=self.git_head, change_id=self.change_id)


class DatasetContext:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.dataset = load_dataset(self.root)
        self.dataset_id = self.dataset["dataset_id"]
        self.dir_rules, self.doc_rules = load_rules(self.root, self.dataset)
        self.registry_types = TypeRegistry()
        self.registry_types.load(self.root, self.dataset)
        self.registry_types.validate_references(self.dir_rules, self.doc_rules)
        self.store = RegistryStore(self.root)

    def scan_and_validate(self, scanned: tuple[Any, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Returns (folders, documents, records, relations, diagnostics) as dicts.

        ``scanned`` lets a caller that already walked the tree (to compute the corpus
        digest) pass the result in instead of paying for a second walk.
        """
        if scanned is None:
            scanned = self.scan()
        scanned_folders, scanned_files = scanned
        diags, doc_info = validate_dataset(self.root, self.dataset, scanned_files, self.dir_rules, self.doc_rules,
                                           registry=self.registry_types)

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
            doc_id = _document_id(scanned.rel_path, info.get("front_matter") or {})
            parent = str(Path(scanned.rel_path).parent.as_posix())
            documents.append(Document(
                document_id=doc_id, dataset_id=self.dataset_id, path=scanned.rel_path,
                parent_folder_id=f"folder:{parent}" if parent != "." else "folder:.",
                format=scanned.format, doc_type=str(info.get("doc_type", "unknown")),
                rule_source=str(info.get("rule_source", "default")), hash=scanned.hash, size=scanned.size,
                title=str(info.get("title", "")), status=scanned.status if scanned.status != "ok" else "ok",
            ).to_dict())
        # Records + relations from JSON files.
        records: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []
        record_texts: dict[str, str] = {}
        for doc in documents:
            if doc["format"] != "json" or doc["status"] != "ok":
                continue
            try:
                text = (self.root / doc["path"]).read_text(encoding="utf-8")
            except OSError:
                continue
            # parse_json (not json.loads): hostile nesting must not raise
            # RecursionError out of the CLI.
            value, errors = parse_json(text, max_depth=int((self.dataset.get("limits") or {}).get("max_json_depth", 128)))
            if errors:
                continue
            if not isinstance(value, dict) or "record_id" not in value:
                continue
            records.append({"record_id": str(value["record_id"]), "entity_type": str(value.get("entity_type", "")),
                            "dataset_id": self.dataset_id, "path": doc["path"], "hash": doc["hash"], "data": value})
            record_texts[doc["path"]] = text
            for rel in (value.get("relations") or []):
                if isinstance(rel, dict) and (rel.get("target") or {}).get("id"):
                    edge = {"type_id": str(rel.get("type_id", "")), "source_id": str(value["record_id"]),
                            "target_id": str(rel["target"]["id"]), "dataset_id": self.dataset_id}
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
                       folders: list[dict[str, Any]], documents: list[dict[str, Any]]
                       ) -> list[dict[str, Any]]:
        """Индекс упоминаний md → цели (план entity-catalog З2). Derived, rebuildable."""
        scanned_folders, scanned_files = scanned
        all_paths = {f.rel_path for f in scanned_files}
        return build_mentions(self.root, scanned_files, records, all_paths)

    def history_recorder(self, change_id: str | None = None) -> HistoryRecorder:
        """Рекодер с бэкендом из конфигурации; деградация в embedded видна в `degraded`."""
        backend, degraded = open_backend(self.root, self.dataset)
        recorder = HistoryRecorder(self.root, backend=backend, change_id=change_id)
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
                                        backend=backend, mode=mode)

    def scan(self) -> tuple[Any, Any]:
        """Walk the corpus once, reusing cached hashes for files whose mtime+size held."""
        follow = bool(self.dataset.get("follow_symlinks", False))
        max_bytes = int((self.dataset.get("limits") or {}).get("max_file_bytes", 10485760))
        return scan_dataset(self.root, follow_symlinks=follow, max_file_bytes=max_bytes,
                            hash_cache=self.store.read_stats())

    def rebuild_index(self, force: bool = True) -> dict[str, Any]:
        """Recompute and publish the snapshot. ``force=False`` reuses a valid one."""
        scanned = self.scan()
        digest = corpus_digest(scanned[1], self.store.config_digest())
        if not force:
            meta = self.store.read_current_meta()
            if meta and meta.get("corpus_digest") == digest:
                existing = self.store.load_current()
                if existing is not None:
                    return {"dataset_id": self.dataset_id, "generation_id": existing.get("generation_id"),
                            "corpus_digest": digest, "reused": True,
                            "folders": len(existing.get("folders") or []),
                            "documents": len(existing.get("documents") or []),
                            "records": len(existing.get("records") or []),
                            "relations": len(existing.get("relations") or []),
                            "diagnostics": len(existing.get("diagnostics") or [])}
        folders, documents, records, relations, diagnostics = self.scan_and_validate(scanned)
        mentions = self.build_mentions(scanned, records, folders, documents)
        gen_id = self.store.publish(self.dataset, folders, documents, records, relations, diagnostics, digest,
                                    mentions=mentions)
        self.store.write_stats(scanned[1])
        self.observe_history(scanned[1])
        return {"dataset_id": self.dataset_id, "generation_id": gen_id, "corpus_digest": digest,
                "reused": False, "folders": len(folders), "documents": len(documents),
                "records": len(records), "relations": len(relations), "diagnostics": len(diagnostics)}

    def ensure_index(self) -> dict[str, Any]:
        """The single invalidation point: reuse the snapshot unless the corpus moved.

        Read commands call this, not ``rebuild_index``. A command that only reads must
        not publish, otherwise an unchanged corpus accumulates one snapshot per run.
        """
        scanned = self.scan()
        digest = corpus_digest(scanned[1], self.store.config_digest())
        meta = self.store.read_current_meta()
        if meta and meta.get("corpus_digest") == digest:
            payload = self.store.load_current()
            if payload is not None:
                return payload
        folders, documents, records, relations, diagnostics = self.scan_and_validate(scanned)
        mentions = self.build_mentions(scanned, records, folders, documents)
        self.store.publish(self.dataset, folders, documents, records, relations, diagnostics, digest,
                           mentions=mentions)
        self.store.write_stats(scanned[1])
        self.observe_history(scanned[1])
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
