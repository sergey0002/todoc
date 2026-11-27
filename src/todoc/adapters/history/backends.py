"""Реализации порта истории: ``embedded`` и ``git``.

Решение 2026-11-25: бэкенд определяется один раз при ``init`` и пишется в ``dataset.json``,
а не вычисляется на каждую запись. Датасет не должен менять поведение от того, в какую
папку его переложили. Если git исчез после ``init``, датасет не ломается — происходит
деградация в ``embedded`` с диагностикой ``history.backend_unavailable``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from todoc.adapters.history import objects
from todoc.ports.history import HistoryBackend


class EmbeddedBackend:  # implements HistoryBackend
    """Снимки всегда пишутся в ``.todoc/history/objects/``. Git не требуется."""

    name = "embedded"

    def __init__(self, root: Path) -> None:
        self.root = root

    def available(self) -> bool:
        return True

    def head(self) -> str | None:
        return None

    def read_at(self, revision: str | None, rel_path: str) -> bytes | None:
        if not revision:
            return None
        return objects.read_snapshot(self.root, revision)

    def needs_snapshot(self, rel_path: str, last_revision: str | None) -> bool:
        return True


class GitBackend:  # implements HistoryBackend
    """Содержимое «до» берётся из репозитория; свои снимки — только для пробелов.

    Правило gap-filling: событие журнала создаётся в момент записи, а коммит делает
    пользователь позже или никогда. Если у прошлого события по этому файлу та же опора
    (HEAD), промежуточное состояние из git не восстановить, и тогда пишется свой снимок.
    При дисциплине коммитов объём близок к нулю, без неё — остаётся полным.
    """

    name = "git"

    def __init__(self, root: Path) -> None:
        self.root = root

    def _git(self, *args: str) -> str | None:
        if shutil.which("git") is None:
            return None
        try:
            proc = subprocess.run(("git", *args), cwd=str(self.root), capture_output=True,
                                  text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return None
        return proc.stdout if proc.returncode == 0 else None

    def available(self) -> bool:
        out = self._git("rev-parse", "--is-inside-work-tree")
        return bool(out and out.strip() == "true")

    def head(self) -> str | None:
        out = self._git("rev-parse", "HEAD")
        return out.strip() if out else None

    def read_at(self, revision: str | None, rel_path: str) -> bytes | None:
        if not revision:
            return None
        if shutil.which("git") is None:
            return None
        clean_rel = rel_path.lstrip("./")
        try:
            proc = subprocess.run(("git", "show", f"{revision}:./{clean_rel}"), cwd=str(self.root),
                                  capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        return proc.stdout if proc.returncode == 0 else None

    def needs_snapshot(self, rel_path: str, last_revision: str | None) -> bool:
        # Нет прошлой опоры — снимать не с чем сравнивать, снимок обязателен.
        if not last_revision:
            return True
        return last_revision == self.head()


def detect_backend(root: Path) -> str:
    """``git`` внутри репозитория, иначе ``embedded``. Вызывается один раз при ``init``."""
    return "git" if GitBackend(root).available() else "embedded"


def resolve_backend(root: Path, configured: str | None) -> tuple[HistoryBackend, str | None]:
    """Возвращает ``(backend, degradation_reason)``.

    ``degradation_reason`` не пуст, когда запрошенный бэкенд недоступен и произошёл
    переход на ``embedded`` — вызывающий слой делает из этого диагностику.
    """
    name = configured or detect_backend(root)
    if name == "git":
        backend = GitBackend(root)
        if backend.available():
            return backend, None
        return EmbeddedBackend(root), "git"
    return EmbeddedBackend(root), None
