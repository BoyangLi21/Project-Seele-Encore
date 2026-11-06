"""Finish only the original HQ eaves outside the earlier component crop."""
from pathlib import Path
import argparse,json,hashlib,msvcrt
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import read_box,iter_block_entities


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'hq_station_move/complete_original_eaves';assert not(out/'APPLIED.json').exists()
    rows=json.loads(a.source.read_text('utf8'));pending=[r for r in rows if r['status']=='PENDING_ORIGINAL_HQ_EAVE_TRANSLATION']
    assert len(rows)==48 and len(pending)==32
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-1344,320))
    for r in pending:
        assert r['source_state']==r['target_after']=='minecraft:gray_concrete'
        assert r['source_retire_to']=='minecraft:air' and r['target_state']=='minecraft:stone'
        assert r['target']==[r['source'][0],r['source'][1]-93,r['source'][2]]
        for key,state in (('source',r['source_state']),('target',r['target_state'])):
            q=tuple(r[key]);assert read_box(world,vox.DIM,q,q)[q]==state
            assert not list(iter_block_entities(world,vox.DIM,q,q))
        painter.exact((*r['source'],*r['source']),r['source_state'],r['source_retire_to'],'retire_original_complete_HQ_outer_eave')
        painter.exact((*r['target'],*r['target']),r['target_state'],r['target_after'],'move_original_complete_HQ_outer_eave')
    painter.meta.update(root_author=True,original_producer_mask=str(a.source),source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
        already_moved_middle_16_preserved=True,actors_or_native_progress_changed=False)
    folder=painter.save_plan('original_outer_eaves_translation')
    if not a.apply:return
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('original_outer_eaves_translation',session_lock=lock)
        for r in pending:
            for key,state in (('source','minecraft:air'),('target','minecraft:gray_concrete')):
                q=tuple(r[key]);assert read_box(world,vox.DIM,q,q)[q]==state
        (out/'APPLIED.json').write_text(json.dumps(dict(world_written=True,original_eaves_translated=32,source_cells_retired=32,
            original_middle_band_untouched=True,receipt=receipt),indent=2),'utf8')
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
