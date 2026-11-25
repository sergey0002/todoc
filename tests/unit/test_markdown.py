from todoc.adapters.formats.markdown import heading_path_for, parse_markdown


def test_headings_and_title():
    doc = parse_markdown("# Design\n\n## Decision\n\nText.\n\n### Detail\n\nMore.\n")
    assert doc.title == "Design"
    assert [h.title for h in doc.headings] == ["Design", "Decision", "Detail"]
    assert [h.level for h in doc.headings] == [1, 2, 3]
    assert doc.headings[0].children[0].title == "Decision"


def test_heading_path():
    doc = parse_markdown("# A\n\n## B\n\n### C\n")
    assert heading_path_for(doc.headings, 2) == ["A", "B", "C"]
    assert heading_path_for(doc.headings, 0) == ["A"]


def test_front_matter():
    doc = parse_markdown("---\ntitle: Hello\nid: doc-1\ntags: [a, b]\ndraft: true\n---\n\n# Hello\n")
    assert doc.front_matter["title"] == "Hello"
    assert doc.front_matter["id"] == "doc-1"
    assert doc.front_matter["tags"] == ["a", "b"]
    assert doc.front_matter["draft"] is True
    assert doc.title == "Hello"


def test_no_front_matter():
    doc = parse_markdown("# Only\n")
    assert doc.front_matter == {}
    assert doc.title == "Only"


def test_unclosed_front_matter():
    doc = parse_markdown("---\ntitle: X\n# Body\n")
    assert doc.front_matter == {}


def test_links_and_wikilinks():
    doc = parse_markdown("See [runbook](../ops/runbook.md) and [[Page]] and [[Page#Sec|alias]].\n")
    targets = [link.target for link in doc.links]
    assert "../ops/runbook.md" in targets
    assert "Page" in targets
    assert any(link.is_wikilink for link in doc.links)


def test_code_fence_hash_not_heading():
    doc = parse_markdown("# Real\n\n```\n# Not a heading\n```\n")
    assert [h.title for h in doc.headings] == ["Real"]


def test_duplicate_headings_anchors():
    doc = parse_markdown("# A\n\n## Same\n\n## Same\n")
    anchors = [h.anchor for h in doc.headings]
    assert anchors[1] == "same"
    assert anchors[2] == "same-1"


def test_empty_document():
    doc = parse_markdown("")
    assert doc.title == ""
    assert doc.headings == []
    assert doc.links == []


# --- Кэш парсинга: разбор сериализуется и восстанавливается без потерь (P1-3) ---

SRC = ('---\ntitle: "Заголовок"\n---\n\n# Один\n\n[ссылка](other.md) и [[wiki]].\n\n'
       '## Под\n\n```md\n[в-коде](nope.md)\n```\n')


def test_doc_payload_roundtrip_is_lossless():
    from todoc.adapters.formats.markdown import doc_from_payload, doc_to_payload
    original = parse_markdown(SRC)
    restored = doc_from_payload(doc_to_payload(original))
    key = lambda d: (  # noqa: E731 - короткое сравнение структур
        d.title, d.front_matter,
        [(h.title, h.level, h.line, h.anchor, h.parent_index) for h in d.headings],
        [(l.text, l.target, l.line, l.column, l.is_wikilink, l.end_column) for l in d.links],
        d.warnings, d.errors)
    assert key(restored) == key(original)
    # Дерево children восстанавливается из parent_index тем же проходом.
    assert [[c.title for c in h.children] for h in restored.headings] == \
           [[c.title for c in h.children] for h in original.headings]
    # Текст в кэш не кладётся: потребителям разбора он не нужен.
    assert restored.text == ""


def test_doc_payload_carries_front_matter_warnings():
    from todoc.adapters.formats.markdown import doc_from_payload, doc_to_payload
    doc = parse_markdown('---\nkey: A: B\n---\n\n# Заголовок\n')
    restored = doc_from_payload(doc_to_payload(doc))
    assert restored.warnings == doc.warnings
    assert restored.warnings, "небезопасный front matter обязан дать предупреждение"


def test_doc_from_payload_rejects_a_foreign_version():
    """Запись чужой версии формы — ошибка, а не тихо принятый разбор."""
    import pytest
    from todoc.adapters.formats.markdown import DOC_PAYLOAD_VERSION, doc_from_payload
    with pytest.raises(ValueError):
        doc_from_payload({"version": DOC_PAYLOAD_VERSION + 1, "title": "", "front_matter": {},
                          "headings": [], "links": [], "warnings": [], "errors": []})
