"""Apply only Root-reviewed whole-width north loops in the preserved HQ."""
from pathlib import Path
import argparse,gzip,json,msvcrt
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import read_box,iter_block_entities


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'hq_north_rings';stage='two_original_HQ_north_loops'
    assert not(out/'APPLIED.json').exists()
    r=json.loads((a.candidate/'REPORT.json').read_text('utf8'))
    assert Path(r['world']).resolve()==world and r['holds']==r['static_failures']==0
    rows=json.loads(gzip.decompress((a.candidate/'FULL_COMPOSED_STATES.json.gz').read_bytes()))
    lo=tuple(min(r['pos'][k] for r in rows) for k in range(3));hi=tuple(max(r['pos'][k] for r in rows) for k in range(3))
    before=read_box(world,'projectseele:geofront',lo,hi)
    for row in rows:assert before[tuple(row['pos'])]==row['before']
    preserved={p:t.snbt() for p,t in iter_block_entities(world,'projectseele:geofront',lo,hi)}
    changed=[r for r in rows if r['before']!=r['after']]
    assert len(changed)==2652 and all(tuple(r['pos']) not in preserved for r in changed)
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-1344,320))
    for row in changed:painter.exact((*row['pos'],*row['pos']),row['before'],row['after'],row['owner'])
    painter.meta.update(root_author=True,reviewed_single_candidate=str(a.candidate),new_floor_y=[-554,-457],
        preserve_all_original_rooms=True,full_width=3,original_native_guard_height=1.375,playable=False)
    folder=painter.save_plan(stage)
    if not a.apply:return
    assert not list(folder.glob('applied_*'))
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply(stage,session_lock=lock)
        actual=read_box(world,vox.DIM,lo,hi)
        assert all(actual[tuple(r['pos'])]==r['after'] for r in rows)
        assert {p:t.snbt() for p,t in iter_block_entities(world,vox.DIM,lo,hi)}==preserved
        (out/'APPLIED.json').write_text(json.dumps(dict(world_written=True,receipt=receipt,complete_controlled_cells_verified=len(rows),
            all_existing_block_entities_preserved=len(preserved),source_candidate=str(a.candidate),native_walk_and_visual_pending=True),indent=2),'utf8')
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
