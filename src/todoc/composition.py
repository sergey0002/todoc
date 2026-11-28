"""Default storage wiring for CLI and standalone application entry points."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from todoc.adapters.history.backends import EmbeddedBackend, resolve_backend
from todoc.adapters.history.store import FileHistoryStore

if TYPE_CHECKING:
    from todoc.application.storage import IndexStore, ParseCache
    from todoc.ports.history import HistoryBackend


def default_index(root: Path) -> IndexStore:
    from todoc.application.registry import RegistryStore

    return RegistryStore(root)


def default_parse_cache(root: Path) -> ParseCache:
    from todoc.application.registry import JsonParseCache

    return JsonParseCache(root)


def default_history_store(root: Path) -> FileHistoryStore:
    return FileHistoryStore(root)


def open_history_backend(root: Path, configured: str | None) -> tuple[HistoryBackend, str | None]:
    return resolve_backend(root, configured)


def default_history_backend(root: Path) -> HistoryBackend:
    return EmbeddedBackend(root)
