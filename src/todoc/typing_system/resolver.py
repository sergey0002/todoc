"""Profile resolution: dir_type / doc_type assignment with explicit priorities.

Priority order (constitution §5.1, guide MD-KB §XIII.3):
  1. hard-exclude / boundaries (applied before classification, in scanner)
  2. explicit declaration (front matter / local config)
  3. nearest local config rules, then dataset rules
     (exact path -> exact basename -> glob; priority + literal-segments tie-break;
     equal result from different rules is an error)
  4. reserved-name defaults
  5. generic/unknown
"""

from __future__ import annotations

import re
from typing import Any

# Reserved basenames (exact segment match at any depth).
RESERVED_DIR_TYPES: dict[str, str] = {
    ".research": "research",
    "architecture": "architecture",
    "constitution": "constitution",
    "harness": "harness",
    "glossary": "glossary",
    "plan": "plan",
}

# Алиасов здесь намеренно нет: зарезервированное имя совпадает только буквально.
# Прежнее RESERVED_ALIASES = {"harnes": "harness"} не читалось никем, а по DoD алиас
# возможен только явной конфигурацией правила — захардкоженная таблица опечаток
# противоречила бы и этому, и собственному правилу «never fuzzy».


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile the v1 mask grammar to a regex.

    ``*`` and ``?`` do not cross ``/``; ``**`` as a separate segment means
    zero or more segments; leading ``/`` anchors to root; trailing ``/``
    means directory only (handled by caller).
    """
    pat = pattern
    if pat.startswith("/"):
        pat = pat[1:]
    out: list[str] = []
    i = 0
    n = len(pat)
    while i < n:
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        elif pat[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pat[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pat[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def glob_match(pattern: str, path: str) -> bool:
    return glob_to_regex(pattern).match(path) is not None


def literal_segments(pattern: str) -> int:
    """Number of literal (non-wildcard) segments; higher is more specific."""
    return sum(1 for seg in pattern.split("/") if seg and "*" not in seg and "?" not in seg)


class RuleMatch:
    def __init__(self, rule: dict[str, Any], specificity: int) -> None:
        self.rule = rule
        self.specificity = specificity

    @property
    def priority(self) -> int:
        return int(self.rule.get("priority", 0))

    @property
    def rule_id(self) -> str:
        return str(self.rule.get("id", ""))


def _match_one(rule: dict[str, Any], path: str, basename: str, front_matter: dict[str, Any] | None) -> int | None:
    """Return specificity if rule matches, else None."""
    match = rule.get("match") or {}
    kind = match.get("kind")
    if kind == "directory":
        if "basename" in match:
            return 100 if basename == match["basename"] else None
        if "glob" in match:
            glob = str(match["glob"])
            return literal_segments(glob) if glob_match(glob, path) else None
        return None
    if kind == "file":
        if "glob" in match:
            glob = str(match["glob"])
            return literal_segments(glob) if glob_match(glob, path) else None
        if "front_matter" in match:
            if not front_matter:
                return None
            wanted = match["front_matter"]
            if not isinstance(wanted, dict):
                return None
            if all(front_matter.get(k) == v for k, v in wanted.items()):
                return 200
            return None
        return None
    return None


def resolve_type(
    rules: list[dict[str, Any]],
    path: str,
    basename: str,
    front_matter: dict[str, Any] | None,
    assign_key: str,
    reserved: dict[str, str],
    default: str = "unknown",
) -> tuple[str, str, list[str]]:
    """Resolve a type for path. Returns (type_id, rule_source, conflicts).

    conflicts lists rule ids that tied on priority+specificity but assigned
    different types (ambiguous -> diagnostic, not silent winner).
    """
    # BUG-001: явное объявление assign_key во front matter — высший приоритет
    # (конституция P1-14): значение берётся из объявления, если ни одно правило
    # не назначает то же значение.
    explicit = None
    if front_matter:
        value = front_matter.get(assign_key)
        if isinstance(value, str) and value.strip():
            explicit = value.strip()
    matches: list[RuleMatch] = []
    for rule in rules:
        spec = _match_one(rule, path, basename, front_matter)
        if spec is not None:
            matches.append(RuleMatch(rule, spec))
    if explicit is not None and not any(
            (m.rule.get("assign") or {}).get(assign_key) == explicit for m in matches):
        return explicit, "front-matter", []
    if matches:
        best = max(matches, key=lambda m: (m.priority, m.specificity))
        tied = [m for m in matches if (m.priority, m.specificity) == (best.priority, best.specificity)]
        assigned = {(m.rule.get("assign") or {}).get(assign_key) for m in tied}
        if len(assigned) > 1:
            conflicts = sorted(m.rule_id for m in tied)
            return default, "ambiguous", conflicts
        return str((best.rule.get("assign") or {}).get(assign_key, default)), f"rule:{best.rule_id}", []
    if basename in reserved:
        return reserved[basename], "reserved", []
    return default, "default", []
