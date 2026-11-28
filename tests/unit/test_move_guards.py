"""Adversarial planner/transaction guards, including recovery-state evidence."""
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
import pytest
import todoc.application.move as m
from todoc.service import DatasetContext
from todoc.errors import TodocError, ConflictError


def test_source_rejections_and_byte_cas(kb, monkeypatch):
    doc={'path':'inbox/a.md','document_id':'x','format':'markdown','status':'ok','hash':'stale'}
    for changes, code in [({'format':'json'},'move.source_not_markdown'),({'status':'unreadable'},'move.source_unreadable'),({'path':'SKILL.md'},'move.source_unsupported')]:
        d={**doc,**changes}
        with pytest.raises(TodocError) as exc:m.resolve_source({'documents':[d]},d['path'],None)
        assert exc.value.code==code
    for docs,code in [([], 'move.source_not_found'),([doc,doc], 'move.source_ambiguous')]:
        with pytest.raises(TodocError) as exc:m.resolve_source({'documents':docs},None,'x')
        assert exc.value.code==code
    ctx=DatasetContext(kb)
    with pytest.raises(ConflictError):m.read_bytes(ctx,doc)
    for raw in [None,b'\xff']:
        if raw is None:(kb/doc['path']).unlink()
        else:(kb/doc['path']).write_bytes(raw);doc['hash']=m.digest(raw)
        with pytest.raises(TodocError) as exc:m.read_bytes(ctx,doc)
        assert exc.value.code=='move.source_unreadable'


def test_pin_type_and_metadata_recovery(kb):
    from todoc.application.move_rewrite import rewrite_identity,set_metadata
    doc={'path':'inbox/a.md','document_id':'semantic','doc_type':'note'}
    text,new=rewrite_identity('# A',doc,'notes/b.md',False,True)
    assert new=='semantic' and 'doc_type: "note"' in text
    assert set_metadata('---\nbroken\n','id','x').startswith('---\nid: "x"')
    assert set_metadata('---\ntitle: A\n---\nbody','id','x').endswith('---\nbody')
    assert set_metadata('', 'id', 'x').endswith('---\n')
    rules_path=kb/'.todoc/rules/document-rules.json'
    rules=json.loads(rules_path.read_text())
    rules['rules'].append({'id':'infer-note','match':{'kind':'file','glob':'notes/*.md'},
                           'assign':{'doc_type':'note'},'priority':100})
    rules_path.write_text(json.dumps(rules))
    inferred=kb/'notes/type.md' 
    inferred.write_text('# Type\n\n## Суть\nBody')
    ctx=DatasetContext(kb)
    pinned=m.plan_move(ctx,source='notes/type.md',target='other/type.md',pin_type=True)
    assert pinned.old_type==pinned.new_type=='note'
    unpinned=m.plan_move(ctx,source='notes/type.md',target='other/type.md')
    assert unpinned.old_type=='note' and unpinned.new_type=='unknown' 


def test_apply_all_plan_guards(kb,monkeypatch):
    ctx=DatasetContext(kb);p=m.plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    with pytest.raises(TodocError):m.apply_move(ctx,p,if_plan_hash='')
    with pytest.raises(TodocError) as e:m.apply_move(ctx,p,if_plan_hash=p.plan_hash,if_hash='bad')
    assert e.value.code=='move.hash_mismatch'
    invalid=replace(p,diagnostics=({'severity':'error'},))
    with pytest.raises(TodocError) as e:m.apply_move(ctx,invalid,if_plan_hash=invalid.plan_hash)
    assert e.value.code=='move.validation_failed'
    real=m.plan_move
    monkeypatch.setattr(m,'plan_move',lambda *a,**k:replace(p,old_id='forged'))
    with pytest.raises(TodocError) as e:m.apply_move(ctx,p,if_plan_hash=p.plan_hash)
    assert e.value.code=='move.plan_stale'
    monkeypatch.setattr(m,'plan_move',real)
    for bad in [replace(p,planned_on='1900-01-01'),replace(p,dataset_id='other')]:
        with pytest.raises(TodocError):m.apply_move(ctx,bad,if_plan_hash=bad.plan_hash)


def test_transaction_per_path_compare(kb):
    ctx=DatasetContext(kb)
    with pytest.raises(ConflictError):m.commit_files(ctx,(m.MoveFile('inbox/a.md',b'wrong',None),),kind='doc.move',change_id='x')
    assert not ctx.history_store.read_events(strict=True)


@pytest.mark.parametrize('mode',['exclusive','other_writer','rollback_error'])
def test_transaction_recovery_guards(kb,monkeypatch,mode):
    import todoc.adapters.filesystem.scanner as scanner
    import todoc.application.history as history
    ctx=DatasetContext(kb);p=m.plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    real=scanner.atomic_write
    if mode=='exclusive':
        def write(path,*a,**kw):
            if path==kb/'notes/b.md':
                path.write_bytes(b'other writer');raise FileExistsError('race')
            return real(path,*a,**kw)
        monkeypatch.setattr(scanner,'atomic_write',write)
    else:
        def fail(*a,**kw):
            if mode=='other_writer':(kb/'notes/b.md').write_bytes(b'other writer')
            raise OSError('journal failed')
        monkeypatch.setattr(history,'_record_event_locked',fail)
        if mode=='rollback_error':
            real_unlink=Path.unlink
            def unlink(path,*a,**kw):
                if path==kb/'notes/b.md':raise OSError('rollback deletion failed')
                return real_unlink(path,*a,**kw)
            monkeypatch.setattr(Path,'unlink',unlink)
    with pytest.raises(TodocError) as e:m.apply_move(ctx,p,if_plan_hash=p.plan_hash)
    if mode=='exclusive':assert e.value.code=='move.target_exists'
    else:
        assert e.value.code=='move.rollback_failed'
        assert e.value.result['recovery_required'] and e.value.result['applied'] is None
        assert 'notes/b.md' in e.value.result['recovery_paths']
    assert not ctx.history_store.read_events(strict=True)
    assert (kb/'inbox/a.md').exists() and (kb/'notes/b.md').exists()


def test_overlay_deleted_dependency_and_mentions(kb):
    from todoc.application.validator import build_mentions
    ctx=DatasetContext(kb);folders,scanned=ctx.scan(strict=True)
    assert build_mentions(kb,scanned,[],{'inbox/a.md'},deleted={'inbox/a.md'})==[]
    payload={'documents':[{'path':'owner.md','attributes':{'derived_from':['inbox/a.md@sha256:old']}}]}
    findings=m.stale_findings(ctx,payload,{}, {'inbox/a.md'})
    assert findings[0]['code']=='staleness.dependency_missing'


@pytest.mark.parametrize('change',['new_inbound','untouched','config','folder','date','parser'])
def test_plan_hash_binds_full_corpus_rules_and_date(kb,monkeypatch,change):
    ctx=DatasetContext(kb);p=m.plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    if change=='new_inbound':(kb/'notes/hub.md').write_text('[a](../inbox/a.md)')
    elif change=='untouched':(kb/'notes/unrelated.md').write_text('# unrelated')
    elif change=='config':
        path=kb/'.todoc/rules/document-rules.json';path.write_text(path.read_text()+'\n')
    elif change=='folder':(kb/'notes/.config.json').write_text('{"schema_version":1}')
    elif change=='parser':
        import todoc.adapters.formats.markdown as registry
        monkeypatch.setattr(registry,'PARSER_VERSION','new-parser')
    else:monkeypatch.setattr(m,'today',lambda:'2099-01-01')
    with pytest.raises(TodocError) as e:m.apply_move(ctx,p,if_plan_hash=p.plan_hash)
    assert e.value.code=='move.plan_stale'
    assert (kb/'inbox/a.md').exists() and not ctx.history_store.read_events(strict=True)


@pytest.mark.parametrize('state',['cold','stale','corrupt'])
def test_preview_publishes_nothing_with_index_variants(kb,state):
    ctx=DatasetContext(kb)
    if state!='cold':ctx.rebuild_index(observe=False)
    if state=='corrupt':
        for path in (kb/'.todoc/index').rglob('*.json'):
            path.write_text('broken')
    if state=='stale':(kb/'notes/new.md').write_text('# New')
    before={p.relative_to(kb):p.read_bytes() for p in kb.rglob('*') if p.is_file()}
    m.plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    assert before=={p.relative_to(kb):p.read_bytes() for p in kb.rglob('*') if p.is_file()}
