"""Deterministic lexical search over registry documents (E4/E5, offline)."""

from __future__ import annotations

import re
from bisect import bisect_left
from pathlib import Path
from typing import Any

from todoc.adapters.formats.markdown import Heading, heading_path_for, parse_markdown
from todoc.domain.models import SearchHit

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_\u0400-\u04ff]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _terms(query: str) -> list[str]:
    return tokenize(query)


def _document_text(root: Path, rel_path: str, fmt: str) -> tuple[str, str]:
    """Return ``(match_text, source_text)``.

    Markdown is matched against an enriched string (title + headings first) so
    structural terms rank, but provenance (snippet, ``line_start``/``line_end``)
    must point into the real file, so the unmodified text is kept alongside.
    """
    try:
        text = (root / rel_path).read_text(encoding="utf-8")
    except OSError:
        return "", ""
    if fmt == "markdown":
        doc = parse_markdown(text)
        headings = " ".join(h.title for h in doc.headings)
        return f"{doc.title}\n{headings}\n{text}", text
    return text, text


#: Сколько окон-кандидатов рассматривается. Ограничение нужно, чтобы частый термин
#: в большом файле не превращал поиск в квадратичный; берётся всегда одно и то же
#: начало списка позиций, поэтому выбор остаётся детерминированным.
_MAX_SNIPPET_ANCHORS = 2000


def _snippet(text: str, terms: list[str], max_chars: int = 240) -> tuple[str, int, int, bool]:
    """Окно вокруг **наиболее релевантного** совпадения, а не первого попавшегося.

    Первое вхождение термина часто оказывается в заголовке или оглавлении, и тогда
    сниппет показывает место, где термин только назван, а не обсуждается. Релевантность
    окна — сколько различных терминов запроса в него попало, затем сколько всего вхождений.
    При равенстве выигрывает самое раннее окно: результат детерминирован (P5) и не
    зависит от порядка терминов в запросе.
    """
    lowered = text.lower()
    positions: dict[str, list[int]] = {}
    for term in dict.fromkeys(terms):
        found: list[int] = []
        index = lowered.find(term)
        while index != -1:
            found.append(index)
            index = lowered.find(term, index + 1)
        if found:
            positions[term] = found
    if not positions:
        return text[:max_chars], 1, 1, len(text) > max_chars

    anchors = sorted(set().union(*positions.values()))[:_MAX_SNIPPET_ANCHORS]
    lists = list(positions.values())
    best_key: tuple[int, int, int] | None = None
    start, end = 0, min(len(text), max_chars)
    for pos in anchors:
        cand_start = max(0, pos - max_chars // 3)
        cand_end = min(len(text), cand_start + max_chars)
        distinct = total = 0
        for found in lists:
            lo = bisect_left(found, cand_start)
            hi = bisect_left(found, cand_end)
            if hi > lo:
                distinct += 1
                total += hi - lo
        key = (distinct, total, -cand_start)
        if best_key is None or key > best_key:
            best_key = key
            start, end = cand_start, cand_end
    snippet = text[start:end].replace("\n", " ").strip()
    truncated = end < len(text) or start > 0
    line_start = text.count("\n", 0, start) + 1
    line_end = text.count("\n", 0, end) + 1
    return snippet, line_start, line_end, truncated


def _breadcrumb(headings: list[Heading], line: int) -> tuple[str, ...]:
    """Breadcrumb of the heading enclosing ``line`` (1-based file line).

    The previous implementation returned the document's first three headings,
    which is a table of contents rather than the path to the matched fragment.
    """
    if not headings:
        return ()
    index = 0
    for i, heading in enumerate(headings):
        if heading.line > line:
            break
        index = i
    return tuple(heading_path_for(headings, index))


def search_documents(
    root: Path,
    documents: list[dict[str, Any]],
    query: str,
    doc_type: str | None = None,
    within: str | None = None,
    limit: int = 10,
    budget: int | None = None,
    offset: int = 0,
) -> tuple[list[SearchHit], int, bool]:
    """Return (hits, total, truncated). Deterministic rank, tie-break by id.

    ``offset`` implements cursor pagination: ``total`` always describes the whole
    result set, ``hits`` only the requested page, and ``truncated`` says whether
    more pages follow the returned one.
    """
    terms = _terms(query)
    if not terms:
        return [], 0, False
    candidates: list[tuple[int, dict[str, Any], str, list[str]]] = []
    for doc in documents:
        if doc.get("status") not in ("ok", None):
            continue
        if doc_type is not None and doc.get("doc_type") != doc_type:
            continue
        if within is not None:
            path = str(doc.get("path", ""))
            if path != within and not path.startswith(within.rstrip("/") + "/"):
                continue
        # Мьют скилов (план skills-vault §4): !-сегмент пути исключает документ
        # из дефолтной выдачи; мьют — свойство хранилища, не параметр запроса.
        if any(part.startswith("!") for part in Path(str(doc.get("path", ""))).parts):
            continue
        match_text, source_text = _document_text(root, str(doc.get("path", "")), str(doc.get("format", "")))
        lowered = match_text.lower()
        matched = [t for t in terms if t in lowered]
        if not matched:
            continue
        title = str(doc.get("title", ""))
        title_hits = sum(1 for t in matched if t in title.lower())
        score = title_hits * 10 + len(matched)
        candidates.append((score, doc, source_text, matched))
    candidates.sort(key=lambda c: (-c[0], str(c[1].get("document_id", ""))))
    total = len(candidates)
    page = candidates[offset:offset + limit]
    hits: list[SearchHit] = []
    used_bytes = 0
    for rank, (_score, doc, text, matched) in enumerate(page, start=offset + 1):
        snippet, line_start, line_end, snippet_trunc = _snippet(text, matched)
        if budget is not None:
            cost = len(snippet.encode("utf-8"))
            if used_bytes + cost > budget and hits:
                break
            used_bytes += cost
        heading_path: tuple[str, ...] = ()
        if doc.get("format") == "markdown":
            try:
                md = parse_markdown((root / str(doc.get("path", ""))).read_text(encoding="utf-8"))
                heading_path = _breadcrumb(md.headings, line_start)
            except OSError:
                heading_path = ()
        hits.append(SearchHit(
            id=str(doc.get("document_id", "")),
            path=str(doc.get("path", "")),
            title=str(doc.get("title", "")),
            heading_path=heading_path,
            rank=rank,
            relevance_method="lexical",
            matched_terms=tuple(matched),
            snippet_text=snippet,
            line_start=line_start,
            line_end=line_end,
            snippet_truncated=snippet_trunc,
        ))
    truncated = total > offset + len(hits)
    return hits, total, truncated
