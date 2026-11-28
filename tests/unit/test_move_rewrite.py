import json
import pytest
from todoc.application.move_rewrite import *
from todoc.application.move import plan_move
from todoc.service import DatasetContext


def test_links_code_record_and_related(kb):
    (kb/'notes/hub.md').write_text('[a](../inbox/a.md#part "title")\n[[a|alias]]\n`[a](../inbox/a.md)`')
    (kb/'inbox/a.md').write_text((kb/'inbox/a.md').read_text()+'\n[hub](../notes/hub.md) [term](term:x#/title)')
    (kb/'notes/term.json').write_text(json.dumps({'record_id':'term:x','entity_type':'term','title':'X'}))
    # Existing record targets are resolved before paths.
    text,n=rewrite_links('[term](term:x#/title)', 'inbox/a.md','inbox/a.md','notes/b.md',set(),{'term:x'})
    assert n==0
    p=plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/b.md')
    hub=next(f.after.decode() for f in p.files if f.path=='notes/hub.md')
    assert '[a](b.md#part "title")' in hub and '[[b|alias]]' in hub and '`[a](../inbox/a.md)`' in hub


def test_reference_and_ambiguity(kb):
    (kb/'notes/hub.md').write_text('[a][r]\n\n[r]: ../inbox/a.md')
    with pytest.raises(ValidationError,match='proven'):plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/b.md')
    (kb/'notes/hub.md').write_text('[[a]]');(kb/'other/b.md').write_text('# B')
    with pytest.raises(ValidationError,match='Ambiguous'):plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/b.md')


def test_metadata_and_baseline():
    old={'related':['[[a#part|x]]'],'covers':['doc:inbox/a.md'],'sources':['inbox/a.md','http://x'], 'baseline':{'artifacts':{'inbox/a.md':'old'}}}
    new=rewrite_attributes(old,source='inbox/a.md',target='notes/b.md',old_id='doc:inbox/a.md',new_id='doc:notes/b.md',paths={'inbox/a.md'},record_ids=set())
    assert new['related']==['[[b#part|x]]'] and new['baseline']['artifacts']=={'notes/b.md':'old'}
    assert new['covers']==['doc:notes/b.md'] and old['covers']==['doc:inbox/a.md']
    old['baseline']['artifacts']['notes/b.md']='collision'
    with pytest.raises(ConflictError):rewrite_attributes(old,source='inbox/a.md',target='notes/b.md',old_id='x',new_id='y',paths=set(),record_ids=set())


def test_reanchor_preserves_drift_and_invalidates_ack():
    oldhash=fragment_hash_text('old',{})[0]
    attrs={'derived_from':[f'a.md@{oldhash}'], 'stale_ack_hashes':[oldhash]}
    new,w=rewrite_dependencies(attrs,'old','new','a.md','b.md','owner.md')
    assert parse_anchor(new['derived_from'][0])['hash']==fragment_hash_text('new',{})[0]
    assert new['stale_ack_hashes']==[] and w
    attrs['derived_from']=['a.md@sha256:old-drift']
    new,w=rewrite_dependencies(attrs,'old','new','a.md','b.md','owner.md')
    assert parse_anchor(new['derived_from'][0])['hash']=='sha256:old-drift' and w


def test_generated_and_json_metadata_and_cycle(kb):
    (kb/'notes/mirror.json').write_text(json.dumps({'record_id':'document:a','entity_type':'document','source_path':'inbox/a.md'}))
    (kb/'notes/dep.json').write_text(json.dumps({'meta':{'derived_from':['inbox/a.md@sha256:stale']},'body':{}}))
    p=plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/b.md')
    assert json.loads(next(f.after for f in p.files if f.path=='notes/mirror.json'))['source_path']=='notes/b.md'
    data=json.loads(next(f.after for f in p.files if f.path=='notes/dep.json')); assert data['meta']['derived_from']==['notes/b.md@sha256:stale']
    text=(kb/'inbox/a.md').read_text().replace('doc_type: note','doc_type: note\nderived_from: ["inbox/a.md@sha256:cyclic"]')
    (kb/'inbox/a.md').write_text(text)
    with pytest.raises(ValidationError,match='Cyclic'):plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/b.md')


def test_rewrite_noops_and_unrelated_metadata():
    assert rewrite_links('[a](a.md)','inbox/a.md','inbox/a.md','inbox/b.md',{'inbox/a.md'},set())==('[a](b.md)',1)
    assert rewrite_links('[b](b.md)','inbox/a.md','inbox/a.md','inbox/c.md',{'inbox/a.md','inbox/b.md'},set())==('[b](b.md)',0)
    attrs={'related':[42,'unrelated'], 'derived_from':[None,{},'other.md@sha256:x'], 'stale_ack_hashes':'unrelated'}
    assert rewrite_attributes(attrs,source='a',target='b',old_id='a',new_id='b',paths=set(),record_ids=set())==attrs
    assert rewrite_dependencies(attrs,'before','after','a','b','owner')[0]==attrs
    attrs={'derived_from':['a@sha256:old'], 'stale_ack_hashes':['not-matching']}
    assert rewrite_dependencies(attrs,'before','after','a','b','owner')[0]['stale_ack_hashes']==['not-matching']
    attrs={'derived_from':['a#section:missing@sha256:old'], 'stale_ack_hashes':['not-matching']}
    assert rewrite_dependencies(attrs,'before','after','a','b','owner')[1]


def test_unrelated_dependency_cycle_and_json_array(kb):
    # A cycle outside the moved node must terminate graph traversal without
    # falsely rejecting a source that merely depends on it.
    text=(kb/'inbox/a.md').read_text().replace('doc_type: note','doc_type: note\nderived_from: ["notes/x.md@sha256:old"]')
    (kb/'inbox/a.md').write_text(text)
    (kb/'notes/x.md').write_text('---\nderived_from: ["notes/y.md@sha256:old"]\n---\n# X')
    (kb/'notes/y.md').write_text('---\nderived_from: ["notes/x.md@sha256:old"]\n---\n# Y')
    (kb/'notes/list.json').write_text('[]')
    original=(kb/'notes/list.json').read_bytes()
    plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/b.md')
    assert (kb/'notes/list.json').read_bytes()==original


@pytest.mark.parametrize('mode',['changed','target','normalized','outside','unaffected'])
def test_active_delta_target_blocks_affected_move(kb,mode):
    d=kb/'changes/x/deltas';d.mkdir(parents=True)
    path='inbox/a.md' if mode=='target' else 'notes/../inbox/a.md' if mode=='normalized' else '../outside.md' if mode=='outside' else 'notes/untouched.md'
    text='---\ntarget: '+path+'\n---\n## ADDED: ## New\n'
    if mode=='changed':text+='[a](../../../inbox/a.md)'
    (d/'a.md').write_text(text)
    if mode in ('outside','unaffected'):
        plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/b.md')
    else:
        with pytest.raises(ConflictError) as e:plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/b.md')
        assert e.value.code=='move.active_change_conflict'


def test_secondary_stale_reported_not_acked(kb):
    from todoc.application.staleness import fragment_hash
    hub=kb/'notes/hub.md';hub.write_text('[a](../inbox/a.md)')
    before=fragment_hash(kb,{'path':'notes/hub.md'})[0]
    # The owner already has an unrelated stale dependency with the SAME code.
    # A code+owner-only comparison would hide the new secondary stale.
    owner=kb/'notes/owner.md'
    owner.write_text('---\nderived_from: '+json.dumps(['inbox/a.md@sha256:old',f'notes/hub.md@{before}'])+'\n---\n# Owner')
    p=plan_move(DatasetContext(kb),source='inbox/a.md',target='notes/b.md')
    assert len(p.new_stale)==1 and p.new_stale[0]['evidence'].startswith('notes/hub.md@')
    assert any(d['code']=='move.preexisting_stale' for d in p.diagnostics)


@pytest.mark.parametrize('name',['file a.md','file#hash.md','file%value.md'])
def test_uri_encoding_roundtrip(kb,name):
    from urllib.parse import quote
    from todoc.application.move import apply_move
    (kb/'notes/hub.md').write_text('[a](../inbox/a.md#part "keep title")')
    ctx=DatasetContext(kb);p=plan_move(ctx,source='inbox/a.md',target='notes/'+name)
    hub=next(f.after.decode() for f in p.files if f.path=='notes/hub.md')
    assert f']({quote(name,safe="/.-_~")}#part "keep title")' in hub
    apply_move(ctx,p,if_plan_hash=p.plan_hash)
    mentions=DatasetContext(kb).read_index()['mentions']
    assert any(m['target']=='notes/'+name for m in mentions)
