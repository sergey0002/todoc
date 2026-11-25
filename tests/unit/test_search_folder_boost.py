# tests/unit/test_search_folder_boost.py — Задача 5 плана folder-config
from pathlib import Path

from todoc.application.search import search_documents


def _doc(root: Path, rel: str) -> dict:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Заметка\n\nсозвон по релизу в среду.\n", encoding="utf-8")
    return {"document_id": rel, "path": rel, "doc_type": "note",
            "format": "markdown", "status": "ok", "title": "Заметка"}


def _setup(tmp_path: Path) -> list[dict]:
    """Одинаковые по тексту документы: notes/ — с конфигом (tags «созвон»), misc/ — без."""
    d = tmp_path / "notes"
    d.mkdir(parents=True)
    (d / ".config.json").write_text(
        '{"schema_version": 1, "title": "Встречи", "aliases": "созвоны|созвон", "tags": ["созвон"]}',
        encoding="utf-8")
    return [_doc(tmp_path, "notes/a.md"), _doc(tmp_path, "misc/b.md")]


def test_query_tag_boosts_config_child_above_equal_doc(tmp_path):
    docs = _setup(tmp_path)
    hits, total, truncated = search_documents(tmp_path, docs, "созвон")
    assert (total, truncated) == (2, False)
    assert hits[0].path == "notes/a.md"  # буст +2 за конфиг-предка с тегом «созвон»
    assert hits[1].path == "misc/b.md"


def test_query_miss_keeps_plain_order(tmp_path):
    docs = _setup(tmp_path)
    hits, _, _ = search_documents(tmp_path, docs, "релиз")
    assert [h.path for h in hits] == ["misc/b.md", "notes/a.md"]  # буст = 0, tie-break по id


def test_query_alias_token_boosts_config_child(tmp_path):
    """Токен alias конфига-предка тоже даёт буст (ветка aliases в cfg_tokens)."""
    docs = _setup(tmp_path)
    hits, total, _ = search_documents(tmp_path, docs, "созвон созвоны")
    assert total == 2  # «созвон» матчит тело, «созвоны» — токен alias конфига
    assert hits[0].path == "notes/a.md"
