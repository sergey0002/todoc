"""Deterministic lexical search over registry documents (E4/E5, offline)."""

from __future__ import annotations

import re
from bisect import bisect_left
from pathlib import Path
from typing import Any

from todoc.adapters.filesystem.scanner import read_verified_text
from todoc.adapters.formats.markdown import Heading, heading_path_for, parse_markdown
from todoc.application.folder_config import load_folder_configs
from todoc.domain.models import SearchHit

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_\u0400-\u04ff]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _terms(query: str) -> list[str]:
    return tokenize(query)


def _document_text(root: Path, rel_path: str, fmt: str,
                   expected_hash: str | None = None, projection: dict[str, Any] | None = None
                   ) -> tuple[str, str, dict[str, Any], list[Heading]]:
    """Return match text, source text, metadata and headings from one parse.

    Markdown is matched against an enriched string (title + headings first) so
    structural terms rank, but provenance (snippet, ``line_start``/``line_end``)
    must point into the real file, so the unmodified text is kept alongside.
    Front matter возвращается третьим элементом (план doc-tags З2): теги участвуют
    в score с весами — второй парсинг файла запрещён, читатель один.
    """
    if expected_hash is not None:
        text = read_verified_text(root, rel_path, expected_hash)
    else:
        try:
            text = (root / rel_path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return "", "", {}, []
    if fmt == "markdown":
        if projection is None:
            parsed = parse_markdown(text)
            title, front_matter, outline = parsed.title, parsed.front_matter, parsed.headings
        else:
            title = projection["title"]
            front_matter = projection["attributes"]
            outline = [Heading(**heading) for heading in projection["headings"]]
        headings = " ".join(heading.title for heading in outline)
        return f"{title}\n{headings}\n{text}", text, front_matter, outline
    return text, text, {}, []


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
    tag: str | None = None,
    *,
    verify_sources: bool = False,
) -> tuple[list[SearchHit], int, bool]:
    """Return (hits, total, truncated). Deterministic rank, tie-break by id.

    ``offset`` implements cursor pagination: ``total`` always describes the whole
    result set, ``hits`` only the requested page, and ``truncated`` says whether
    more pages follow the returned one.
    """
    terms = _terms(query)
    if not terms:
        return [], 0, False
    # Задача 5 плана folder-config: низковесный буст по конфигам папок-предков.
    # Один load_folder_configs на вызов; токены конфига считаются один раз.
    folder_configs, _fc_diags = load_folder_configs(root)
    cfg_tokens: dict[str, frozenset[str]] = {}
    for rel, fc in folder_configs.items():
        toks = set(tokenize(" ".join([fc.title or "", fc.description or "", " ".join(fc.tags)])))
        for alias in fc.aliases:
            toks.update(tokenize(alias))
        cfg_tokens[rel] = frozenset(toks)
    candidates: list[tuple[int, dict[str, Any], str, list[str], list[Heading]]] = []
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
        match_text, source_text, front_matter, headings = _document_text(
            root, str(doc.get("path", "")), str(doc.get("format", "")),
            doc["hash"] if verify_sources else None, doc if verify_sources else None,
        )
        tags = [x for x in (front_matter.get("tags") or []) if isinstance(x, str)]
        if tag is not None and tag.lower() not in {t.lower() for t in tags}:
            continue  # план doc-tags З2: --tag — точный пост-фильтр по тегу
        lowered = match_text.lower()
        matched = [t for t in terms if t in lowered]
        if not matched:
            continue
        title = str(doc.get("title", ""))
        attributes = doc.get("attributes") or {}
        mirrors_document = (doc.get("format") == "json" and attributes.get("entity_type") == "document"
                            and isinstance(attributes.get("source_path"), str))
        # A catalog record repeats a source title; that repetition should not
        # receive the authoring document's title boost.
        title_hits = 0 if mirrors_document else sum(1 for t in matched if t in title.lower())
        score = title_hits * 10 + len(matched)
        # План doc-tags З2: тег exact ×8, пословно внутри kebab-тега ×3 — аддитивно
        # поверх базового score (title ×10 + len(matched) + cfg-буст folder-config);
        # документы без тегов — прежний score.
        lowered_tags = {t.lower() for t in tags}
        tag_exact = sum(1 for t in lowered_tags if t in set(matched))
        tag_partial = sum(1 for t in lowered_tags for part in t.split("-")
                          if part and part in set(matched) and t not in set(matched))
        score += tag_exact * 8 + tag_partial * 3
        if cfg_tokens:
            rel_path = Path(str(doc.get("path", "")))
            for anc in rel_path.parents:
                key = anc.as_posix()
                if key != "." and key in cfg_tokens:
                    if any(term in tok for tok in cfg_tokens[key] for term in terms):
                        score += 2  # несколько конфигов-предков суммируются
        candidates.append((score, doc, source_text, matched, headings))
    candidates.sort(key=lambda c: (-c[0], str(c[1].get("document_id", ""))))
    total = len(candidates)
    page = candidates[offset:offset + limit]
    hits: list[SearchHit] = []
    used = 0
    for rank, (_score, doc, text, matched, headings) in enumerate(page, start=offset + 1):
        snippet, line_start, line_end, snippet_trunc = _snippet(text, matched)
        if budget is not None:
            remaining = budget - used
            if len(snippet) > remaining:
                if hits:
                    break
                snippet = snippet[:remaining]
                snippet_trunc = True
            used += len(snippet)
        heading_path = _breadcrumb(headings, line_start)
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
