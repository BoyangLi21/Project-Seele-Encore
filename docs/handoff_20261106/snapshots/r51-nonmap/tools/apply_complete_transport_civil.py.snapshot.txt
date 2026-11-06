"""Apply one explicitly reviewed transport civil candidate, never its MTR data."""
from pathlib import Path
import argparse,gzip,json,msvcrt
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import read_box,iter_block_entities


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--stage',required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    assert a.stage.replace('_','').isalnum()
    base=a.base.resolve();world=base/'WORLD';out=base/'transport_civil'/a.stage
    assert not(out/'APPLIED.json').exists()
    report=json.loads((a.candidate/'REPORT.json').read_text('utf8'))
    assert Path(report['source_world']).resolve()==world and report['world_written'] is False
    assert report.get('holds',0)==0
    with gzip.open(a.candidate/'COMPLETE_SOURCE_AND_TARGET.jsonl.gz','rt',encoding='utf8') as f:rows=[json.loads(s) for s in f]
    assert len({tuple(r['pos']) for r in rows})==len(rows)
    lo=tuple(min(r['pos'][k] for r in rows) for k in range(3));hi=tuple(max(r['pos'][k] for r in rows) for k in range(3))
    # This entry currently admits one complete bounded U2 stock tunnel. Broad
    # multi-line excavation needs its own sparse section preflight.
    assert report['schema']=='projectseele.complete-map.U2-siding-civil.candidate.v1'
    assert lo==(-166,-563,517) and hi==(-12,-554,532)
    before=read_box(world,'projectseele:geofront',lo,hi)
    before_be={p:t.snbt() for p,t in iter_block_entities(world,'projectseele:geofront',lo,hi)}
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-1344,320))
    for r in rows:
        q=tuple(r['pos']);assert before[q]==r['before'] and before_be.get(q)==r['before_nbt']
        assert r['before_nbt'] is None and r['after_nbt'] is None
        if r['before']!=r['after']:painter.exact((*q,*q),r['before'],r['after'],r['owner'])
    painter.meta.update(root_author=True,reviewed_candidate=str(a.candidate),mtr_data_changed=False,
        keep_original_HQ_platform_devices=True,staff_width=3,staff_foot_y=-559,playable=False)
    folder=painter.save_plan(a.stage)
    if not a.apply:return
    assert not list(folder.glob('applied_*'))
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply(a.stage,session_lock=lock)
        actual=read_box(world,vox.DIM,lo,hi)
        assert all(actual[tuple(r['pos'])]==r['after'] for r in rows)
        assert {p:t.snbt() for p,t in iter_block_entities(world,vox.DIM,lo,hi)}==before_be
        (out/'APPLIED.json').write_text(json.dumps(dict(world_written=True,receipt=receipt,full_component_cells_read_back=len(rows),
            native_mtr_metadata_not_yet_installed=True,original_platform_BEs_preserved=len(before_be),
            pending=['original track formation retirement','native MTR paths/vehicle progress installation','actual riding and visual review']),indent=2),'utf8')
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
