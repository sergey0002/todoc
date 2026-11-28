import json
import pytest
from todoc.service import DatasetContext
from todoc.application.move import plan_move, validate_files, MoveFile
from todoc.errors import ValidationError


def test_overlay_equals_real_validation_and_mentions(kb):
    (kb/'notes/hub.md').write_text('[a](../inbox/a.md#part)')
    ctx=DatasetContext(kb);ctx.rebuild_index(observe=False)
    plan=plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    virtual=validate_files(ctx,plan.files)
    assert not (kb/'notes/b.md').exists()
    for f in plan.files:
        if f.after is None:(kb/f.path).unlink()
        else:(kb/f.path).write_bytes(f.after)
    actual=ctx.read_index()
    for field in ('documents','records','relations','mentions','diagnostics'):assert virtual[field]==actual[field]


def test_error_baseline_and_new_error(kb):
    (kb/'notes/hub.md').write_text('[missing](missing.md)')
    with pytest.raises(ValidationError) as e:plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/b.md')
    assert e.value.code=='move.baseline_invalid'
    (kb/'notes/hub.md').unlink()
    with pytest.raises(ValidationError) as e:validate_files(DatasetContext(kb),(MoveFile('notes/new.md',None,b'[x](missing.md)'),))
    assert e.value.code=='move.validation_failed'


def test_json_record_overlay_and_deleted(kb):
    ctx=DatasetContext(kb)
    raw=json.dumps({'record_id':'term:x','entity_type':'term','title':'X'}).encode()
    virtual=validate_files(ctx,(MoveFile('notes/term.json',None,raw),MoveFile('notes/hub.md',None,b'[[term:x]]'),MoveFile('inbox/a.md',(kb/'inbox/a.md').read_bytes(),None)))
    assert virtual['records'][0]['record_id']=='term:x'
    assert virtual['mentions'][0]['target']=='term:x'
    assert not any(d['path']=='inbox/a.md' for d in virtual['documents'])
