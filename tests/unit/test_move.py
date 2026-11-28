from pathlib import Path
import pytest
from todoc.config import init_dataset
from todoc.service import DatasetContext
from todoc.application.move import plan_move, checked_path, resolve_source, MoveFile, digest
from todoc.errors import TodocError


def test_plan_readonly_and_identity(kb):
    ctx=DatasetContext(kb)
    before={str(p):p.read_bytes() for p in kb.rglob('*') if p.is_file()}
    p=plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    assert p.new_id=='doc:notes/b.md' and b'id: "doc:notes/b.md"' in p.files[0].after
    assert p.plan_hash==plan_move(ctx,doc_id='doc:inbox/a.md',target='notes/b.md').plan_hash
    assert before=={str(p):p.read_bytes() for p in kb.rglob('*') if p.is_file()}
    assert p.plan_hash!=plan_move(ctx,source='inbox/a.md',target='notes/b.md',keep_id=True).plan_hash

@pytest.mark.parametrize('raw',['../a.md','/a.md','C:/a.md','a\\b.md','.git/a.md','notes/../a.md','notes/CON.md','notes/a?.md','notes/a.'])
def test_bad_paths(kb,raw):
    with pytest.raises(TodocError):checked_path(kb,raw,portable=True)

@pytest.mark.parametrize('target,code',[('inbox/a.md','move.same_path'),('inbox/A.md','move.case_only_rename'),('missing/a.md','move.target_dir_missing'),('missing/','move.target_dir_missing'),('notes/a.txt','move.extension_mismatch')])
def test_bad_targets(kb,target,code):
    with pytest.raises(TodocError) as e:plan_move(DatasetContext(kb),source='inbox/a.md',target=target)
    assert e.value.code==code

def test_target_folder_keep_id_no_front_matter(kb):
    (kb/'inbox/a.md').write_text('# A')
    p=plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/',keep_id=True,pin_type=True)
    assert p.target=='notes/a.md' and p.new_id=='doc:inbox/a.md'
    assert b'id: "doc:inbox/a.md"' in p.files[0].after

def test_symlinks_and_target_exists(kb):
    (kb/'notes/a.md').symlink_to(kb/'missing')
    with pytest.raises(TodocError,match='Symlink'):plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/a.md')
    (kb/'notes/a.md').unlink();(kb/'notes/a.md').write_text('# B')
    with pytest.raises(TodocError,match='already exists'):plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/a.md')


def test_apply_and_readset(kb):
    from todoc.application.move import apply_move
    ctx=DatasetContext(kb);p=plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    (kb/'notes/new.md').write_text('# New')
    with pytest.raises(TodocError) as e:apply_move(ctx,p,if_plan_hash=p.plan_hash)
    assert e.value.code=='move.plan_stale'
    p=plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    out=apply_move(ctx,p,if_plan_hash=p.plan_hash)
    assert out['applied'] and out['committed'] and out['index_published']
    assert not (kb/'inbox/a.md').exists() and (kb/'notes/b.md').exists()
    assert len(ctx.history_store.read_events(strict=True))==1


@pytest.mark.parametrize('failure',['write','delete','history','index','cache'])
def test_failure_matrix(kb,monkeypatch,failure):
    from todoc.application.move import apply_move, MoveFailure
    import todoc.adapters.filesystem.scanner as scanner
    import todoc.application.history as history
    ctx=DatasetContext(kb)
    (kb/'notes/hub.md').write_text('[a](../inbox/a.md)')
    original={p.relative_to(kb).as_posix():p.read_bytes() for p in kb.rglob('*') if p.is_file() and '.todoc' not in p.parts}
    plan=plan_move(ctx,source='inbox/a.md',target='notes/b.md')
    def fail(*a,**kw):raise OSError('injected')
    if failure=='write':
        real=scanner.atomic_write
        def write(path,*a,**kw):
            if path.name=='hub.md' and a[0]!=original['notes/hub.md']:raise OSError('write failed')
            return real(path,*a,**kw)
        monkeypatch.setattr(scanner,'atomic_write',write)
    elif failure=='delete':
        real=Path.unlink
        def unlink(path,*a,**kw):
            if path==kb/'inbox/a.md':raise OSError('delete failed')
            return real(path,*a,**kw)
        monkeypatch.setattr(Path,'unlink',unlink)
    elif failure=='history':monkeypatch.setattr(history,'_record_event_locked',fail)
    elif failure=='index':monkeypatch.setattr(DatasetContext,'rebuild_index',fail)
    else:monkeypatch.setattr(ctx.parse_cache,'invalidate',fail)
    with pytest.raises(MoveFailure) as e:apply_move(ctx,plan,if_plan_hash=plan.plan_hash)
    if failure in ('index','cache'):
        assert e.value.result['committed'] and not e.value.result['index_published']
        assert not (kb/'inbox/a.md').exists()
    else:
        assert not e.value.result['committed']
        assert original=={p.relative_to(kb).as_posix():p.read_bytes() for p in kb.rglob('*') if p.is_file() and '.todoc' not in p.parts}
        assert not ctx.history_store.read_events(strict=True)
