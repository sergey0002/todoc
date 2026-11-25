"""Markdown adapter: headings/links/front matter from tokens, never regex for links.

Uses markdown-it-py (CommonMark) token stream as the authority for headings
and links (so code fences, inline code, reference links and autolinks are
handled by the parser, not by ad-hoc patterns). Regex is used only to locate
the column of an already-confirmed inline link on its raw line, and for
Obsidian wikilinks (which CommonMark does not parse) outside code regions.
Front matter is a separate YAML-lite layer (simple ``key: value`` pairs)
validated independently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote

from markdown_it import MarkdownIt

_MD = MarkdownIt("commonmark")  # shared parser instance (parse is stateless per call)

# Only for column location of token-confirmed inline links, never for discovery.
_INLINE_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:")


@dataclass
class Heading:
    title: str
    level: int
    line: int
    anchor: str
    parent_index: int | None = None
    children: list[Heading] = field(default_factory=list)


@dataclass
class Link:
    text: str
    target: str
    line: int
    column: int
    is_wikilink: bool = False
    end_column: int = 0  # 1-based column of the last char of the markdown span


@dataclass
class MarkdownDoc:
    title: str
    front_matter: dict[str, Any]
    headings: list[Heading]
    links: list[Link]
    text: str
    errors: list[str] = field(default_factory=list)
    warnings: list[tuple[int, str]] = field(default_factory=list)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9\u0400-\u04ff]+", "-", title.lower()).strip("-")
    return slug or "section"


def _yaml_unsafe(value: str) -> bool:
    """True when a bare scalar would break a real YAML parser.

    ``title: Constitution: product`` is rejected by PyYAML/Obsidian with
    "mapping values are not allowed in this context", while our YAML-lite
    reader accepts it. Portability requires quoting such values.
    """
    if not value or value[0] in ("\"", "'", "[", "{", "|", ">"):
        return False
    return ": " in value or value.endswith(":")


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str, int, list[tuple[int, str]]]:
    """Return (front_matter, body, body_start_line_1based, warnings).

    YAML-lite subset: ``key: value`` pairs, ``true``/``false`` booleans and
    inline ``[a, b]`` lists. Numbers stay strings; nested maps and multiline
    blocks are not supported (minimal front matter schema, MD-KB guide).
    Duplicate keys: last wins. Warnings carry (1-based line, message) for
    values a real YAML parser would reject.
    """
    lines = text.splitlines()
    warnings: list[tuple[int, str]] = []
    if not lines or lines[0].strip() != "---":
        return {}, text, 1, warnings
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text, 1, warnings
    fm: dict[str, Any] = {}
    for lineno, raw in enumerate(lines[1:end], start=2):
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip()
        quoted = len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'")
        if _yaml_unsafe(value):
            warnings.append((lineno, f"Значение ключа {key!r} нужно взять в кавычки: "
                                     f"YAML-парсер отклонит незакавыченное {value!r}."))
        if quoted:
            value = value[1:-1]
        if value in ("true", "false"):
            fm[key] = value == "true"
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            fm[key] = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()] if inner else []
        else:
            fm[key] = value
    body = "\n".join(lines[end + 1 :])
    return fm, body, end + 2, warnings


def _inline_text(children: list[Any]) -> str:
    """Plain text of inline children (markup stripped, code kept)."""
    parts: list[str] = []
    for child in children:
        if child.type in ("text", "code_inline"):
            parts.append(child.content or "")
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts)


def _code_regions(tokens: list[Any], body_start: int) -> list[tuple[int, int]]:
    """1-based inclusive line ranges of fenced/indented code and HTML blocks."""
    regions: list[tuple[int, int]] = []
    for tok in tokens:
        if tok.type in ("fence", "code_block", "html_block") and tok.map:
            regions.append((tok.map[0] + body_start, tok.map[1] - 1 + body_start))
    return regions


def _in_regions(line: int, regions: list[tuple[int, int]]) -> bool:
    return any(start <= line <= end for start, end in regions)


def _inline_code_spans(line_text: str) -> list[tuple[int, int]]:
    """0-based [start, end) spans of backtick code spans on one line."""
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(line_text)
    while i < n:
        if line_text[i] == "`":
            j = i
            while j < n and line_text[j] == "`":
                j += 1
            ticks = j - i
            close = line_text.find("`" * ticks, j)
            if close == -1:
                break
            spans.append((i, close + ticks))
            i = close + ticks
        else:
            i += 1
    return spans


def _token_links(tokens: list[Any], body_start: int) -> list[tuple[str, str, int]]:
    """Authoritative (text, href, line_1based) links/images from inline tokens."""
    found: list[tuple[str, str, int]] = []
    for tok in tokens:
        if tok.type != "inline" or not tok.children:
            continue
        line = (tok.map[0] + body_start) if tok.map else body_start
        current_href: str | None = None
        current_text: list[str] = []
        current_line = line
        for child in tok.children:
            if child.type in ("softbreak", "hardbreak"):
                line += 1
                if current_href is not None:
                    current_text.append(" ")
            elif child.type == "link_open":
                current_href = str((child.attrs or {}).get("href", ""))
                current_text = []
                current_line = line
            elif child.type == "image":
                href = str((child.attrs or {}).get("src", ""))
                found.append(((child.content or "").strip(), href, line))
            elif child.type == "link_close":
                # markdown-it always pairs link_close with a preceding link_open.
                found.append(("".join(current_text).strip(), current_href or "", current_line))
                current_href = None
                current_text = []
            elif current_href is not None and child.type in ("text", "code_inline"):
                current_text.append(child.content or "")
    return found


def _locate_columns(
    raw_links: list[tuple[str, str, int]], body_lines: list[str], body_start: int
) -> list[Link]:
    """Attach columns to token links via per-line regex correlation.

    Inline links get exact columns from the raw line; reference links and
    autolinks (no regex match) fall back to searching for ``[``/``<``.
    """
    by_line: dict[int, list[int]] = {}
    for idx, (_text, _href, line) in enumerate(raw_links):
        by_line.setdefault(line, []).append(idx)
    columns: dict[int, tuple[int, int]] = {}
    for line, idxs in by_line.items():
        raw_line = body_lines[line - body_start] if 0 <= line - body_start < len(body_lines) else ""
        matches = list(_INLINE_LINK_RE.finditer(raw_line))
        used: set[int] = set()
        for idx in idxs:
            text, href, _line = raw_links[idx]
            match = None
            for mi, m in enumerate(matches):
                if mi not in used and m.group(2) == href:
                    match = m
                    used.add(mi)
                    break
            if match is None:
                for mi, m in enumerate(matches):
                    if mi not in used:
                        match = m
                        used.add(mi)
                        break
            if match is not None:
                columns[idx] = (match.start() + 1, match.end())
            elif href.startswith(_EXTERNAL_PREFIXES) or text == href:
                pos = raw_line.find("<")
                columns[idx] = (pos + 1, pos + 1 + len(text) + 1) if pos >= 0 else (1, 1)
            else:
                pos = raw_line.find("[" + text)
                columns[idx] = (pos + 1, pos + 1 + len(text) + 2) if pos >= 0 else (1, 1)
    links: list[Link] = []
    for idx, (text, href, line) in enumerate(raw_links):
        column, end_column = columns.get(idx, (1, 1))
        target = href if href.startswith(_EXTERNAL_PREFIXES) else unquote(href)
        links.append(Link(text=text, target=target, line=line, column=column, end_column=end_column))
    return links


def _wikilinks(body_lines: list[str], body_start: int, regions: list[tuple[int, int]]) -> list[Link]:
    links: list[Link] = []
    for offset, raw_line in enumerate(body_lines):
        lineno = body_start + offset
        if _in_regions(lineno, regions):
            continue
        code_spans = _inline_code_spans(raw_line)
        for m in _WIKILINK_RE.finditer(raw_line):
            if any(start <= m.start() < end for start, end in code_spans):
                continue
            links.append(Link(text=m.group(1).strip(), target=m.group(1).strip(),
                              line=lineno, column=m.start() + 1, is_wikilink=True, end_column=m.end()))
    return links


def parse_markdown(text: str) -> MarkdownDoc:
    if text.startswith("\ufeff"):
        text = text[1:]
    front_matter, body, body_start, fm_warnings = _parse_front_matter(text)
    tokens = _MD.parse(body)
    headings: list[Heading] = []
    stack: list[tuple[int, int]] = []  # (level, index)
    seen_anchors: dict[str, int] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])
            line = (tok.map[0] + body_start) if tok.map else body_start
            # markdown-it always emits an inline token after heading_open;
            # `children or []` keeps this safe if a plugin changes that.
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            title = _inline_text(inline.children or []).strip() if inline is not None else ""
            base = _slugify(title)
            count = seen_anchors.get(base, 0)
            anchor = base if count == 0 else f"{base}-{count}"
            seen_anchors[base] = count + 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else None
            headings.append(Heading(title=title, level=level, line=line, anchor=anchor, parent_index=parent))
            stack.append((level, len(headings) - 1))
        i += 1
    # Build tree children.
    for idx, h in enumerate(headings):
        if h.parent_index is not None:
            headings[h.parent_index].children.append(h)

    body_lines = body.splitlines()
    raw_links = _token_links(tokens, body_start)
    links = _locate_columns(raw_links, body_lines, body_start)
    links.extend(_wikilinks(body_lines, body_start, _code_regions(tokens, body_start)))
    links.sort(key=lambda link: (link.line, link.column))

    title = ""
    if front_matter.get("title"):
        title = str(front_matter["title"])
    elif headings:
        title = headings[0].title
    return MarkdownDoc(title=title, front_matter=front_matter, headings=headings, links=links,
                       text=text, warnings=fm_warnings)


def resolve_link_target(source_path: str, target: str) -> str | None:
    """Normalize a link target to a root-relative path (pure, no filesystem).

    Returns None for external URLs, mailto, anchor-only and empty targets.
    Fragments (``#section``) are stripped; ``.``/``..`` are resolved lexically.
    """
    if target.startswith(_EXTERNAL_PREFIXES + ("#",)):
        return None
    target_path = target.split("#")[0]
    if not target_path:
        return None
    parent_dir = PurePosixPath(source_path).parent
    resolved = (parent_dir / target_path).as_posix()
    parts: list[str] = []
    for part in resolved.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def build_backlink_index(documents: dict[str, MarkdownDoc]) -> dict[str, list[str]]:
    """Map normalized target path -> sorted source paths linking to it."""
    index: dict[str, set[str]] = {}
    for source_path, doc in documents.items():
        for link in doc.links:
            target = resolve_link_target(source_path, link.target)
            if target:
                index.setdefault(target, set()).add(source_path)
    return {target: sorted(sources) for target, sources in sorted(index.items())}


def heading_path_for(headings: list[Heading], index: int) -> list[str]:
    path: list[str] = []
    cur: Heading | None = headings[index]
    while cur is not None:
        path.append(cur.title)
        cur = headings[cur.parent_index] if cur.parent_index is not None else None
    path.reverse()
    return path


def section_bounds(text: str, selector: str) -> tuple[int, int] | None:
    """Границы раздела в тексте: ``(start, end)``, 1-based, включительно.

    Селектор — ``## Заголовок`` (уровень + текст). Совпадение префиксное, поэтому
    ``## MODIFIED:`` находит ``## MODIFIED: ## Цель``. Раздел заканчивается перед
    следующим заголовком того же или более высокого уровня, иначе — концом файла.
    Возвращает None, когда раздел не найден: вызывающий решает, ошибка это или нет.
    """
    from todoc.typing_system.descriptors import parse_heading_selector

    doc = parse_markdown(text)
    wanted = selector.strip()
    total = len(text.splitlines())
    for index, heading in enumerate(doc.headings):
        title = f"{'#' * heading.level} {heading.title}".strip()
        if not (title == wanted or heading.title == wanted
                or (wanted.endswith(":") and title.startswith(wanted))):
            continue
        end = total
        for later in doc.headings[index + 1:]:
            if later.level <= heading.level:
                end = later.line - 1
                break
        return heading.line, end
    return None


# ---------------------------------------------------------------------------
# Сериализация разбора для кэша парсинга (P1-3)
# ---------------------------------------------------------------------------

#: Версия формы кэша. Любое изменение состава полей обязано её поднять: кэш
#: производный и пересобираемый, а молча прочитанная запись старой формы дала бы
#: диагностику не по тому разбору.
DOC_PAYLOAD_VERSION = 1


def doc_to_payload(doc: MarkdownDoc) -> dict[str, Any]:
    """Разобранный документ как JSON-совместимый словарь.

    Заголовки кладутся плоским списком с ``parent_index`` — дерево ``children``
    восстанавливается из него тем же проходом, что и в ``parse_markdown``, поэтому
    прочитанный из кэша документ неотличим от разобранного заново. ``text`` не
    сохраняется: потребителям разбора нужны заголовки, ссылки и front matter, а
    текст при попадании в кэш всё равно не читается.
    """
    return {
        "version": DOC_PAYLOAD_VERSION,
        "title": doc.title,
        "front_matter": doc.front_matter,
        "headings": [[h.title, h.level, h.line, h.anchor, h.parent_index] for h in doc.headings],
        "links": [[link.text, link.target, link.line, link.column, link.is_wikilink, link.end_column]
                  for link in doc.links],
        "warnings": [[lineno, message] for lineno, message in doc.warnings],
        "errors": list(doc.errors),
    }


def doc_from_payload(payload: dict[str, Any]) -> MarkdownDoc:
    """Обратное к :func:`doc_to_payload`. Бросает исключение на записи чужой формы.

    Исключение намеренно не глотается здесь: решает вызывающий — кэш считает
    такую запись промахом и разбирает файл заново.
    """
    if payload.get("version") != DOC_PAYLOAD_VERSION:
        raise ValueError(f"unsupported markdown cache version: {payload.get('version')!r}")
    headings = [Heading(title=row[0], level=int(row[1]), line=int(row[2]), anchor=row[3],
                        parent_index=None if row[4] is None else int(row[4]))
                for row in payload["headings"]]
    for index, heading in enumerate(headings):
        if heading.parent_index is not None:
            headings[heading.parent_index].children.append(heading)
    links = [Link(text=row[0], target=row[1], line=int(row[2]), column=int(row[3]),
                  is_wikilink=bool(row[4]), end_column=int(row[5]))
             for row in payload["links"]]
    return MarkdownDoc(title=payload["title"], front_matter=payload["front_matter"],
                       headings=headings, links=links, text="",
                       errors=list(payload["errors"]),
                       warnings=[(int(row[0]), str(row[1])) for row in payload["warnings"]])
