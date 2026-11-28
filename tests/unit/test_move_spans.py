import pytest
from todoc.adapters.formats.markdown import editable_link_spans
from todoc.application.write import bump_front_matter_updated

@pytest.mark.parametrize('prefix', ['', '\ufeff'])
@pytest.mark.parametrize('nl', ['\n', '\r\n'])
@pytest.mark.parametrize('end', ['', '\n'])
def test_updated_preserves_bom_crlf_and_final_newline(prefix, nl, end):
    text=prefix+nl.join(['---','updated: 2020-01-01','---','# Title'])+end
    new, changed=bump_front_matter_updated(text, '2026-11-28')
    assert changed and new == text.replace('2020-01-01','2026-11-28')

@pytest.mark.parametrize('text,targets', [
    ('`[example](old.md)` [real](old.md)', ['old.md']),
    ('[ref][r] [real](other.md)\n\n[r]: old.md', [None,'other.md']),
    ('[a](old.md#part) [a](old.md#part)', ['old.md#part']*2),
    ('![a](file%20a.png "title")', ['file%20a.png']),
    ('```md\n[a](old.md)\n```\n    [b](old.md)\n\n[x](old.md)', ['old.md']),
    ('<https://example.org>', [None]),
    ('[[old#part|alias]]', ['old']),
    ('[![pic](a.png)](b.md)', [None,'a.png']),
])
def test_verified_spans(text, targets):
    spans=editable_link_spans(text)
    got=[None if s.destination_start is None else text[s.destination_start:s.destination_end] for s in spans]
    assert sorted(got,key=str)==sorted(targets,key=str)


def test_uneditable_unsafe_schemes_are_not_candidates():
    assert editable_link_spans('[x](javascript:alert)')==[]
