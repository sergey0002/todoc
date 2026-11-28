"""Skills vault scanner (open Agent Skills standard): a folder with SKILL.md is a skill.

Files are the truth, the tree is derived (P1): every call walks the vault live —
no persistent skills index. Deterministic and offline (P5): sorted traversal,
sorted output, no network. The engine never picks a skill and never executes
``scripts/`` — choosing, auditing and executing is the agent's job (план
skills-vault §4, «Границы ответственности»). Mute is a naming convention, not
deletion: a ``!``-prefixed folder keeps a standard-valid ``name`` inside; the
mute applies to placement, not content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import is_within_root
from todoc.adapters.formats.markdown import parse_markdown

#: ``name`` по открытому стандарту Agent Skills: строчные буквы/цифры/дефисы,
#: без ведущих/хвостовых/двойных дефисов, ≤64 символов, совпадает с именем папки.
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NAME_MAX = 64
DESC_MAX = 1024

_RESOURCE_DIRS = ("references", "scripts", "assets")


@dataclass
class SkillInfo:
    """One detected skill: metadata only, no content read into memory."""

    name: str
    path: str  # skill folder, posix, relative to the vault root
    skill_md: str  # SKILL.md path, posix, relative to the vault root
    section: str  # parent folder path ("" for a vault-top-level skill)
    description: str
    muted: bool
    refs: int
    scripts: int
    assets: int


def effective_name(folder: str) -> str:
    """Folder name without the mute prefix: ``!legacy-deploy`` -> ``legacy-deploy``."""
    return folder.lstrip("!")


def _diag(path: str, code: str, message: str, line: int | None = None,
          suggested_fixes: list[str] | None = None) -> dict[str, Any]:
    """House diagnostic shape (cf. Diagnostic.to_dict) without dataset binding.

    The validator wrapper fills dataset_id/id when merging into a dataset run;
    direct callers (CLI import report) embed these dicts as-is.
    """
    return {
        "dataset_id": "",
        "id": "",
        "code": code,
        "severity": "error",
        "path": path,
        "message": message,
        "location": {"line": line} if line else {},
        "evidence": "",
        "suggested_fixes": suggested_fixes or [],
    }


def _count_dir(folder: Path, name: str) -> int:
    d = folder / name
    return sum(1 for p in d.iterdir() if p.is_file()) if d.is_dir() else 0


def scan_skills(vault_root: Path) -> tuple[list[SkillInfo], list[dict[str, Any]]]:
    """Walk the vault, return ``(skills, per-file diagnostics)``.

    Leaf-detect: a directory containing SKILL.md is a skill; any other directory
    is a section. Sections nest arbitrarily; a skill may sit at any depth,
    including the vault root (``section == ""``). Unknown front matter keys
    (Claude Code / Hermes extensions) are ignored — we are not the only reader.
    """
    skills: list[SkillInfo] = []
    diags: list[dict[str, Any]] = []
    if not vault_root.is_dir():
        return skills, diags
    for md in sorted(vault_root.rglob("SKILL.md")):
        folder = md.parent
        rel_md = md.relative_to(vault_root).as_posix()
        if not is_within_root(vault_root, md):
            diags.append(_diag(rel_md, "access.outside_data_root", "SKILL.md находится за пределами vault."))
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            diags.append(_diag(rel_md, "skills.missing_front_matter",
                               "SKILL.md не читается как UTF-8.", 1,
                               ["Пересохраните файл в UTF-8 без BOM."]))
            continue
        try:
            doc = parse_markdown(text)
        except Exception:  # noqa: BLE001 — парсер не должен ронять скан
            diags.append(_diag(rel_md, "skills.missing_front_matter",
                               "SKILL.md не парсится как markdown.", 1,
                               ["Проверьте синтаксис front matter (YAML между ---)."]))
            continue
        fm = doc.front_matter if isinstance(doc.front_matter, dict) else {}
        if not fm:
            diags.append(_diag(rel_md, "skills.missing_front_matter",
                               "SKILL.md без валидного front matter (name/description).", 1,
                               ["Добавьте YAML front matter: name, description."]))
            continue
        name = str(fm.get("name") or "")
        desc = str(fm.get("description") or "")
        if not NAME_RE.match(name) or len(name) > NAME_MAX:
            diags.append(_diag(rel_md, "skills.bad_name",
                               f"name «{name or '∅'}» не соответствует стандарту "
                               f"(regex {NAME_RE.pattern}, ≤{NAME_MAX}).", 1,
                               [f"Переименуйте name в kebab-case латиницей и папку так же."]))
        eff = effective_name(folder.name)
        if name and name != eff:
            diags.append(_diag(rel_md, "skills.name_mismatch",
                               f"name «{name}» не совпадает с именем папки «{eff}».", 1,
                               [f"Сделайте name = «{eff}» или переименуйте папку в «{name}»."]))
        if not desc.strip():
            diags.append(_diag(rel_md, "skills.empty_description",
                               "description пуст: стандарт требует «что делает + когда».", 1,
                               ["Опишите скил одной строкой: WHAT + WHEN + NOT-WHEN."]))
        elif len(desc) > DESC_MAX:
            diags.append(_diag(rel_md, "skills.long_description",
                               f"description {len(desc)} симв. > {DESC_MAX} по стандарту.", 1,
                               ["Сократите описание; детали — в тело SKILL.md или references/."]))
        skills.append(SkillInfo(
            name=name or eff,
            path=folder.relative_to(vault_root).as_posix(),
            skill_md=rel_md,
            section=folder.parent.relative_to(vault_root).as_posix()
            if folder != vault_root and folder.parent != vault_root else "",
            description=desc,
            muted=any(part.startswith("!") for part in folder.relative_to(vault_root).parts),
            refs=_count_dir(folder, "references"),
            scripts=_count_dir(folder, "scripts"),
            assets=_count_dir(folder, "assets"),
        ))
    # Детерминизм (P5) с учётом мьюта: «!legacy-deploy» сортируется как
    # «legacy-deploy», поэтому ключ — путь без «!»-префиксов сегментов.
    skills.sort(key=lambda s: "/".join(p.lstrip("!") for p in s.path.split("/")))
    return skills, diags


def validate_skills(vault_root: Path, skills: list[SkillInfo]) -> list[dict[str, Any]]:
    """Cross-file checks that per-file scanning cannot see (duplicate names)."""
    diags: list[dict[str, Any]] = []
    seen: dict[str, SkillInfo] = {}
    for skill in skills:
        first = seen.get(skill.name)
        if first is None:
            seen[skill.name] = skill
            continue
        diags.append(_diag(
            skill.skill_md, "skills.duplicate_name",
            f"name «{skill.name}» уже занят ({first.path}); стандарт требует уникальность "
            f"по всему vault.", 1,
            [f"Переименуйте один из скилов ({first.path}, {skill.path})."]))
    return diags
