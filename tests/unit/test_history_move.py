import pytest
from todoc.application.history import record_event, content_at, before_content, log
from todoc.adapters.history.store import FileHistoryStore


def test_event_exact_exists_and_legacy_reads(kb):
    store=FileHistoryStore(kb)
    before=(kb/'inbox/a.md').read_bytes()
    rev=record_event(kb,[{'path':'inbox/a.md','before':before,'after':None},
                         {'path':'notes/b.md','before':None,'after':b''}],kind='doc.move',change_id='move:test',store=store)
    (kb/'inbox/a.md').unlink();(kb/'notes/b.md').write_bytes(b'')
    events=store.read_events(strict=True);assert len(events)==1
    assert events[0]['paths'][0]['after_exists'] is False
    assert store.read_snapshot(events[0]['paths'][0]['before'])==before
    assert content_at(kb,rev,'inbox/a.md',store=store)==(None,'missing')
    assert before_content(kb,rev,'inbox/a.md',store=store)==(before,'ok')
    assert before_content(kb,rev,'notes/b.md',store=store)==(None,'no_before')
    assert content_at(kb,rev,'notes/b.md',store=store)==(b'','ok')


def test_journal_failed_atomic_publish_keeps_prefix(kb,monkeypatch):
    import todoc.adapters.history.store as mod
    store=FileHistoryStore(kb)
    record_event(kb,[],kind='baseline',store=store)
    path=kb/'.todoc/history/journal.jsonl';before=path.read_bytes()
    def fail(*a,**kw):raise OSError('disk full')
    monkeypatch.setattr(mod,'atomic_write',fail)
    with pytest.raises(OSError):record_event(kb,[{'path':'x','before':b'old','after':None}],kind='doc.move',store=store)
    assert path.read_bytes()==before and len(store.read_events(strict=True))==1


def test_move_revert_exact_bytes_and_no_overwrite(kb):
    from todoc.application.move import plan_move, apply_move
    from todoc.application.history import plan_revert_event, revert_event
    from todoc.service import DatasetContext
    from todoc.errors import ConflictError
    ctx=DatasetContext(kb)
    original=(kb/'inbox/a.md').read_bytes().replace(b'\n',b'\r\n').rstrip(b'\r\n')
    (kb/'inbox/a.md').write_bytes(b'\xef\xbb\xbf'+original)
    before=(kb/'inbox/a.md').read_bytes()
    p=plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    moved=apply_move(ctx,p,if_plan_hash=p.plan_hash)
    (kb/'notes/b.md').write_bytes(b'later')
    with pytest.raises(ConflictError):plan_revert_event(ctx,moved['change_id'])
    (kb/'notes/b.md').write_bytes(p.files[0].after)
    reverse=plan_revert_event(ctx,moved['change_id'])
    result=revert_event(ctx,moved['change_id'],if_plan_hash=reverse['plan_hash'])
    assert result['applied'] and (kb/'inbox/a.md').read_bytes()==before
    assert not (kb/'notes/b.md').exists()
    with pytest.raises(ConflictError):plan_revert_event(ctx,moved['change_id'])
    assert len(ctx.history_store.read_events(strict=True))==2
    p=plan_move(ctx,source='inbox/a.md',target='notes/b.md');again=apply_move(ctx,p,if_plan_hash=p.plan_hash)
    assert again['change_id']!=moved['change_id']


def test_reverse_validates_new_inbound_and_hash(kb):
    from todoc.application.move import plan_move, apply_move
    from todoc.application.history import plan_revert_event, revert_event
    from todoc.service import DatasetContext
    from todoc.errors import TodocError
    ctx=DatasetContext(kb);p=plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    moved=apply_move(ctx,p,if_plan_hash=p.plan_hash)
    reverse=plan_revert_event(ctx,moved['change_id'])
    with pytest.raises(TodocError):revert_event(ctx,moved['change_id'],if_plan_hash='wrong')
    (kb/'notes/hub.md').write_text('[b](b.md)')
    with pytest.raises(TodocError) as e:plan_revert_event(ctx,moved['change_id'])
    assert e.value.code=='move.validation_failed'


@pytest.mark.parametrize('mode,code',[('missing','move.revert_not_found'),('ambiguous','move.revert_ambiguous'),('legacy','move.revert_unsupported'),('snapshot','move.revert_unsupported'),('empty','move.revert_unsupported'),('duplicate','move.revert_unsupported')])
def test_revert_event_history_guards(kb,mode,code):
    from todoc.application.history import plan_revert_event
    from todoc.service import DatasetContext
    from todoc.errors import TodocError
    ctx=DatasetContext(kb)
    entries=[] if mode=='empty' else [{'path':'notes/new.md','before':b'old','after':None}]
    if mode=='legacy':
        ctx.history_store.append_event({'kind':'doc.move','change_id':'move:x','paths':[{'path':'notes/new.md','before':None,'after':None}]})
    elif mode!='missing':
        if mode=='duplicate':entries*=2
        record_event(kb,entries,kind='doc.move',change_id='move:x',store=ctx.history_store)
        if mode=='ambiguous':record_event(kb,[],kind='doc.move',change_id='move:x',store=ctx.history_store)
        if mode=='snapshot':
            from todoc.adapters.history.objects import object_path,content_hash
            object_path(kb,content_hash(b'old')).unlink()
    with pytest.raises(TodocError) as e:plan_revert_event(ctx,'move:x')
    assert e.value.code==code


def test_revert_requires_hash_and_content_before_creation(kb):
    from todoc.application.history import revert_event
    from todoc.service import DatasetContext
    from todoc.errors import TodocError
    with pytest.raises(TodocError):revert_event(DatasetContext(kb),'move:x',if_plan_hash='')
    record_event(kb,[{'path':'notes/new.md','before':None,'after':b'new'}],kind='doc.move')
    assert content_at(kb,None,'notes/new.md')==(None,'missing')


def test_content_at_before_explicit_creation(kb):
    store=FileHistoryStore(kb)
    rev=record_event(kb,[],kind='baseline',store=store)
    record_event(kb,[{'path':'new.md','before':None,'after':b'new'}],kind='doc.move',store=store)
    (kb/'new.md').write_bytes(b'new')
    assert content_at(kb,rev,'new.md',store=store)==(None,'missing')
