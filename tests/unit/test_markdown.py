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
