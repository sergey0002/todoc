"""Staleness: fragment-anchored dependencies (``derived_from``) and acknowledgement.

A dependency is not a file, it is a *fragment* of a file. Hashing the whole file would
mark a document stale whenever anything at all changed in its source, which makes the
diagnostic noise rather than signal. Anchors reuse what the codebase already parses:
``jsonfmt.resolve_pointer`` for JSON Pointer, ``markdown.parse_markdown`` for sections.

Acknowledgement is stored next to the source, not in ``.todoc/``: whether a drift is
relevant is human knowledge, and P1 keeps truth in the files.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from todoc.adapters.formats.jsonfmt import parse_json, resolve_pointer
from todoc.adapters.formats.markdown import parse_markdown
from todoc.domain.models import Diagnostic

DEPENDENCY_MISSING = "staleness.dependency_missing"
DEPENDENCY_CHANGED = "staleness.dependency_changed"

#: Front matter keys that carry an acknowledgement. Flat on purpose: the markdown
#: front matter layer is YAML-lite (``key: value`` plus inline ``[a, b]`` lists), so a
#: nested per-dependency map could not be written back there.
ACK_AT = "stale_acknowledged_at"
ACK_REASON = "stale_ack_reason"
ACK_HASHES = "stale_ack_hashes"


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    """Stable serialisation: key order and separators must not move the hash."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _section_lines(text: str, selector: str) -> list[str] | None:
    """Lines of one markdown section, heading included, up to the next same-level heading."""
    doc = parse_markdown(text)
    wanted = selector.strip()
    headings = doc.headings
    for index, heading in enumerate(headings):
        title = f"{'#' * heading.level} {heading.title}".strip()
        if not (title == wanted or heading.title == wanted or title.startswith(wanted + " ")):
            continue
        start = heading.line
        end = len(text.splitlines())
        for later in headings[index + 1 :]:
            if later.level <= heading.level:
                end = later.line - 1
                break
        return text.splitlines()[start - 1 : end]
    return None


def fragment_hash(root: Path, dep: dict[str, Any]) -> tuple[str | None, str]:
    """Hash of the fragment a dependency points at.

    Returns ``(hash, status)`` where status is ``ok``, ``missing``, ``unreadable`` or
    ``unresolved`` (the file is there but the pointer/section no longer is). A missing
    fragment is reported distinctly from a missing file because the remedies differ:
    one is a renamed anchor, the other a deleted source.
    """
    rel = str(dep.get("path") or "")
    target = root / rel
    if not target.is_file():
        return None, "missing"
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, "unreadable"
    pointer = dep.get("pointer")
    if pointer is not None:
        value, errors = parse_json(text)
        if errors:
            return None, "unresolved"
        try:
            return _sha256(_canonical(resolve_pointer(value, str(pointer)))), "ok"
        except (KeyError, IndexError, ValueError):
            return None, "unresolved"
    section = dep.get("section")
    if section is not None:
        lines = _section_lines(text, str(section))
        if lines is None:
            return None, "unresolved"
        return _sha256("\n".join(lines).strip()), "ok"
    return _sha256(text), "ok"


def parse_anchor(raw: str) -> dict[str, Any] | None:
    """Parse the compact anchor form used in markdown front matter.

    ``path[#fragment]@sha256:…`` where fragment is a JSON Pointer (``/meta/date``) or
    ``section:<heading>``. Returns None when the string cannot be an anchor, so a typo
    in front matter surfaces as a malformed dependency rather than a silent no-op.
    """
    if not isinstance(raw, str) or "@" not in raw:
        return None
    head, _, digest = raw.rpartition("@")
    if not digest.startswith("sha256:"):
        return None
    dep: dict[str, Any] = {"path": head, "hash": digest}
    if "#" in head:
        path, _, fragment = head.partition("#")
        dep["path"] = path
        if fragment.startswith("section:"):
            dep["section"] = fragment[len("section:") :]
        elif fragment.startswith("/"):
            dep["pointer"] = fragment
        else:
            return None
    return dep if dep["path"] else None


def format_anchor(dep: dict[str, Any]) -> str:
    path = str(dep.get("path") or "")
    if dep.get("section") is not None:
        path = f"{path}#section:{dep['section']}"
    elif dep.get("pointer") is not None:
        path = f"{path}#{dep['pointer']}"
    return f"{path}@{dep.get('hash') or ''}"


def dependencies_of(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise ``derived_from`` from either a record (objects) or front matter (strings)."""
    raw = source.get("derived_from")
    out: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("path"):
                out.append(item)
            elif isinstance(item, str):
                parsed = parse_anchor(item)
                if parsed:
                    out.append(parsed)
    return out


def _ack_hashes(owner: dict[str, Any]) -> set[str]:
    raw = owner.get(ACK_HASHES)
    if isinstance(raw, list):
        return {str(h) for h in raw}
    if isinstance(raw, str) and raw:
        return {raw}
    return set()


def check_owner(dataset_id: str, owner_path: str, owner: dict[str, Any], root: Path,
                line: int | None = None) -> list[Diagnostic]:
    """Compare every dependency of one owner against the live corpus."""
    acked = _ack_hashes(owner)
    acked_at = owner.get(ACK_AT)
    diagnostics: list[Diagnostic] = []
    for dep in dependencies_of(owner):
        rel = str(dep.get("path"))
        expected = str(dep.get("hash") or "")
        actual, status = fragment_hash(root, dep)
        anchor = format_anchor(dep)
        if status == "missing":
            diagnostics.append(Diagnostic(
                dataset_id=dataset_id,
                id=_diag_id(owner_path, DEPENDENCY_MISSING, anchor),
                code=DEPENDENCY_MISSING, severity="warning", path=owner_path,
                location={"line": line} if line else {},
                evidence=anchor,
                message=f"Зависимость отсутствует: {rel}. Файл удалён или перемещён.",
            ))
            continue
        if status in ("unreadable", "unresolved"):
            diagnostics.append(Diagnostic(
                dataset_id=dataset_id,
                id=_diag_id(owner_path, DEPENDENCY_CHANGED, anchor),
                code=DEPENDENCY_CHANGED, severity="warning", path=owner_path,
                location={"line": line} if line else {},
                evidence=anchor,
                message=f"Якорь зависимости не разрешается ({status}): {anchor}. "
                        f"Указатель или заголовок больше не существует в {rel}.",
            ))
            continue
        if actual == expected:
            continue
        # Acknowledged and unchanged since: the owner saw this exact fragment already.
        if acked_at and actual in acked:
            continue
        diagnostics.append(Diagnostic(
            dataset_id=dataset_id,
            id=_diag_id(owner_path, DEPENDENCY_CHANGED, anchor),
            code=DEPENDENCY_CHANGED, severity="warning", path=owner_path,
            location={"line": line} if line else {},
            evidence=f"{anchor} ожидался {expected or '—'}, фактически {actual}",
            message=f"Зависимость изменилась: {rel}. Фрагмент, от которого зависит этот "
                    f"документ, больше не совпадает.",
        ))
    return diagnostics


def _diag_id(owner_path: str, code: str, anchor: str) -> str:
    return hashlib.sha256(f"{owner_path}|{code}|{anchor}".encode("utf-8")).hexdigest()[:16]


def collect_owners(root: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Owners that declare dependencies: markdown front matter and JSON records.

    The index carries no front matter, so the source files are read here. Only paths the
    index already knows about are opened, which keeps the command bounded by the corpus
    it is asked about rather than by the filesystem.
    """
    owners: list[dict[str, Any]] = []
    for doc in payload.get("documents") or []:
        rel = str(doc.get("path") or "")
        if doc.get("format") != "markdown":
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm = parse_markdown(text).front_matter
        if not isinstance(fm, dict) or "derived_from" not in fm:
            continue
        owners.append({"path": rel, "kind": "document", "source": fm})
    for record in payload.get("records") or []:
        data = record.get("data")
        if not isinstance(data, dict) or "derived_from" not in data:
            continue
        owners.append({"path": str(record.get("path") or ""), "kind": "record", "source": data})
    return owners


def check_all(dataset_id: str, root: Path, payload: dict[str, Any],
              only_path: str | None = None) -> list[Diagnostic]:
    """Every staleness diagnostic in the dataset, or for one owner path."""
    diagnostics: list[Diagnostic] = []
    for owner in collect_owners(root, payload):
        if only_path and owner["path"] != only_path:
            continue
        diagnostics.extend(check_owner(dataset_id, owner["path"], owner["source"], root))
    return diagnostics


def current_hashes(root: Path, owner: dict[str, Any]) -> list[str]:
    """Hashes of the owner's dependencies as they are right now — what an ack records."""
    hashes = []
    for dep in dependencies_of(owner.get("source") or {}):
        actual, status = fragment_hash(root, dep)
        if status == "ok" and actual:
            hashes.append(actual)
    return hashes


def plan_ack(root: Path, rel_path: str, reason: str, at: str,
             current: list[str]) -> str:
    """Return the new text of a markdown document with an acknowledgement recorded.

    Only the front matter block is rewritten; the body is preserved byte for byte. The
    recorded hashes are the fragments' *current* hashes, so the acknowledgement lapses
    the moment any of them moves again.
    """
    text = (root / rel_path).read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{rel_path}: нет блока front matter, подтверждение некуда записать")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError(f"{rel_path}: блок front matter не закрыт")
    fm_lines = [ln for ln in lines[1:end]
                if not ln.split(":", 1)[0].strip() in (ACK_AT, ACK_REASON, ACK_HASHES)]
    hashes = ", ".join(f'"{h}"' for h in current)
    fm_lines.append(f'{ACK_AT}: "{at}"')
    fm_lines.append(f'{ACK_REASON}: "{reason.replace(chr(34), chr(39))}"')
    fm_lines.append(f"{ACK_HASHES}: [{hashes}]")
    body = "\n".join(lines[end + 1 :])
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + (body + "\n" if body else "")
