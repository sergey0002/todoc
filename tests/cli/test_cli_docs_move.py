import json
from pathlib import Path
import pytest
from click.testing import CliRunner
from todoc.cli import cli, main
from todoc.config import init_dataset

@pytest.fixture
def root(tmp_path):
    root=tmp_path/'kb';root.mkdir();init_dataset(root)
    (root/'inbox').mkdir();(root/'notes').mkdir()
    (root/'inbox/a.md').write_text('---\nid: doc:inbox/a.md\ndoc_type: note\n---\n# A\n\n## Суть\n\nТекст.\n')
    return root

def run(root,*args):return CliRunner().invoke(cli,['--root',str(root),*args])
def body(result):
    assert result.exit_code==0,(result.output,result.exception)
    return json.loads(result.output)


def test_cli_move_apply_revert_next_actions(root):
    preview=body(run(root,'docs','move','--from','inbox/a.md','--to','notes/b.md','--verbose'))
    assert preview['data']['result']['preview'] and preview['data']['result']['diff']
    applied=body(CliRunner().invoke(cli,preview['next_actions'][0]['argv'][1:]))
    assert applied['data']['result']['applied'] and not applied['data']['result']['preview']
    reverse=body(CliRunner().invoke(cli,applied['next_actions'][1]['argv'][1:]))
    restored=body(CliRunner().invoke(cli,reverse['next_actions'][0]['argv'][1:]))
    assert restored['data']['result']['committed'] and (root/'inbox/a.md').exists()

@pytest.mark.parametrize('fmt',['json','table','markdown'])
def test_alias_output_and_errors(root,fmt):
    out=run(root,'--output',fmt,'docs','mv','--from','inbox/a.md','--to','notes/b.md')
    assert out.exit_code==0 and 'guidance' in out.output
    out=run(root,'docs','move','--output',fmt,'--from','inbox/a.md','--to','notes/b.md','--apply')
    assert out.exit_code==2 and 'usage.error' in out.output
    assert not (root/'notes/b.md').exists()

def test_selector_and_action_conflicts(root):
    for opts in [[],['--id','doc:inbox/a.md','--from','inbox/a.md'],['--from','inbox/a.md','--preview','--apply']]:
        out=run(root,'docs','move','--to','notes/b.md',*opts)
        assert out.exit_code==2 and json.loads(out.output)['ok'] is False


def test_demo_copy_move_apply_revert(tmp_path):
    import shutil
    from todoc.service import DatasetContext
    root=tmp_path/'demo'
    shutil.copytree(Path(__file__).resolve().parents[2]/'demo',root,
                    ignore=shutil.ignore_patterns('index','cache','history'))
    body(run(root,'docs','new','--apply','--type','note','--title','Move probe','--path','inbox/move-probe.md'))
    home=root/'HOME.md';home.write_bytes(home.read_bytes()+b'\n[probe](inbox/move-probe.md)\n')
    body(run(root,'sync','--apply','HOME.md'))
    def manifest():return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file() and '.todoc' not in p.parts}
    assert body(run(root,'validate','--all'))['diagnostics']==[]
    baseline_stale=body(run(root,'stale'))['diagnostics']
    before=manifest();ctx=DatasetContext(root);event_count=len(ctx.history_store.read_events(strict=True))
    preview=body(run(root,'docs','move','--from','inbox/move-probe.md','--to','notes/move-probe.md'))
    assert manifest()==before
    moved=body(CliRunner().invoke(cli,preview['next_actions'][0]['argv'][1:]))
    assert moved['data']['result']['applied']
    assert body(run(root,'validate','--all'))['diagnostics']==[]
    link_meta=body(run(root,'docs','links','--limit','1000'))['data']['meta']
    assert link_meta['total']==0 and not link_meta['truncated'] and link_meta['next_cursor'] is None
    assert body(run(root,'docs','read','--id',moved['data']['result']['new_id']))['ok']
    assert body(run(root,'docs','tree'))['ok']
    assert body(run(root,'stale'))['diagnostics']==baseline_stale
    reverse=body(run(root,'revert','--change',moved['data']['result']['change_id']))
    body(CliRunner().invoke(cli,reverse['next_actions'][0]['argv'][1:]))
    assert manifest()==before and len(ctx.history_store.read_events(strict=True))==event_count+2
    assert not (root/'notes/move-probe.md').exists()
    assert body(run(root,'stale'))['diagnostics']==baseline_stale


def test_legacy_unicode_source_and_mirror(root):
    (root/'inbox/черновик.md').write_text('---\nid: doc:inbox/черновик.md\ndoc_type: note\n---\n# Черновик\n\n## Суть\n\nТекст.\n')
    (root/'notes/hub.md').write_text('[draft](../inbox/%D1%87%D0%B5%D1%80%D0%BD%D0%BE%D0%B2%D0%B8%D0%BA.md) [[черновик|alias]]')
    (root/'notes/mirror.json').write_text(json.dumps({'record_id':'document:draft','entity_type':'document','source_path':'inbox/черновик.md'}))
    preview=body(run(root,'docs','move','--from','inbox/черновик.md','--to','notes/draft.md'))
    body(CliRunner().invoke(cli,preview['next_actions'][0]['argv'][1:]))
    assert '[[draft|alias]]' in (root/'notes/hub.md').read_text()
    assert json.loads((root/'notes/mirror.json').read_text())['source_path']=='notes/draft.md'


def test_move_failure_commit_state_and_revert_error(root,monkeypatch):
    from todoc.application.move import MoveFailure
    import todoc.application.move as move
    def fail(*a,**kw):raise MoveFailure('move.index_failed',{'applied':True,'committed':True,'index_published':False},'index failed')
    monkeypatch.setattr(move,'apply_move',fail)
    p=body(run(root,'docs','move','--from','inbox/a.md','--to','notes/b.md'))
    out=run(root,'docs','move','--from','inbox/a.md','--to','notes/b.md','--apply','--if-plan-hash',p['data']['result']['plan_hash'])
    assert out.exit_code==6
    response=json.loads(out.output)
    assert response['data']['result']['committed'] and str(root) in response['next_actions'][0]['argv']
    out=run(root,'revert','--change','move:missing')
    assert out.exit_code==6 and json.loads(out.output)['data']['result']['applied'] is False
    for fmt in ['table','markdown']:
        out=run(root,'docs','move','--output',fmt,'--from','inbox/a.md','--to','notes/b.md','--apply','--if-plan-hash',p['data']['result']['plan_hash'])
        assert out.exit_code==6 and 'committed' in out.output and 'guidance' in out.output
    out=run(root,'docs','move','--root',str(root),'--root',str(root),'--from','inbox/a.md','--to','notes/b.md')
    assert out.exit_code==2 and json.loads(out.output)['data']['result']['applied'] is False
    for args in [('revert','rev','--change','x'),('revert',),('revert','rev','--path','x','--if-plan-hash','h')]:
        out=run(root,*args)
        assert getattr(out.exception,'exit_code',out.exit_code)==2


def test_bounded_summary_id_selector_and_options(root):
    for i in range(23):(root/f'notes/hub-{i}.md').write_text('[a](../inbox/a.md)')
    out=body(run(root,'docs','move','--id','doc:inbox/a.md','--to','notes/b.md','--keep-id','--pin-type'))
    result=out['data']['result']
    assert result['files_total']==25 and result['files_returned']==20 and result['files_truncated']
    assert 'diff' not in result and result['old_id']==result['new_id']
    assert '--keep-id' in out['next_actions'][0]['argv'] and '--pin-type' in out['next_actions'][0]['argv']
    body(CliRunner().invoke(cli,out['next_actions'][0]['argv'][1:]))
