"""Install Root-reviewed original compact-car retirement with exact rollback."""
from pathlib import Path
import argparse
import gzip
import json
import msvcrt
import nbtlib
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import read_box,iter_block_entities
from prepare_complete_lift_followups import prepare_capability_merge
from apply_s20_approved_semantic_repairs import atomic_replace
from verify_main_r20 import entities

DIM='projectseele:geofront'
STAGE='original_compact_lift_dead_stops_retired'


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True)
    p.add_argument('--civil',type=Path,required=True);p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'compact_lift_retirement'
    assert not (out/'APPLIED.json').exists()
    report=json.loads((a.civil/'REPORT.json').read_text('utf8'))
    assert Path(report['world']).resolve()==world and report['holds']==report['static_failures']==0
    rows=json.loads(gzip.decompress((a.civil/'FULL_COMPOSED_STATES.json.gz').read_bytes()))
    bes=json.loads((a.civil/'BLOCK_ENTITY_FINAL.json').read_text('utf8'))['rows']
    lo=tuple(min(r['pos'][k] for r in rows) for k in range(3));hi=tuple(max(r['pos'][k] for r in rows) for k in range(3))
    measured=read_box(world,DIM,lo,hi)
    for r in rows:assert measured[tuple(r['pos'])]==r['before'],('Original compact component changed',r['pos'])
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM=DIM
    painter=vox.Painter(vertical_bounds=(-1344,320))
    for r in rows:
        if r['before']!=r['after']:painter.exact((*r['pos'],*r['pos']),r['before'],r['after'],r['owner'])
    for r in bes:
        pos=tuple(r['pos']);before=None if r['before_nbt'] is None else nbtlib.parse_nbt(r['before_nbt'])
        after=None if r['after_nbt'] is None else nbtlib.parse_nbt(r['after_nbt'])
        if before is not None and after is not None:painter.update_block_entity(pos,r['state'],before,after,'compact_original_controller_label')
        elif after is not None:painter.block_entities[pos]=after
    painter.meta.update(root_author=True,original_car_preserved=True,source_car_floor=-394,target_car_floor=-442,
        actual_remaining_floors=[-468,-442],main_lifts_added=0,playable=False)
    folder=painter.save_plan(STAGE)
    if not a.apply:return
    assert not list(folder.glob('applied_*'))
    lock=extension.acquire_world_lock();geometry=None;cap=None
    try:
        current=dict(iter_block_entities(world,DIM,lo,hi))
        for r in bes:
            tag=current.get(tuple(r['pos']))
            assert (None if tag is None else tag.snbt())==r['before_nbt']
        before_entities={k:v.snbt() for k,v in entities(world).items()}
        assert len(before_entities)==678
        cap=prepare_capability_merge(world,a.metadata)
        backup=folder/'capabilities_before.dat';backup.write_bytes(cap['before'])
        geometry=painter.apply(STAGE,session_lock=lock)
        assert cap['path'].read_bytes()==cap['before'];atomic_replace(cap['path'],cap['after'])
        after=read_box(world,DIM,lo,hi)
        assert all(after[tuple(r['pos'])]==r['after'] for r in rows)
        current=dict(iter_block_entities(world,DIM,lo,hi))
        for r in bes:
            tag=current.get(tuple(r['pos']))
            assert (None if tag is None else tag.snbt())==r['after_nbt']
        assert {k:v.snbt() for k,v in entities(world).items()}==before_entities
        assert cap['path'].read_bytes()==cap['after']
        result=dict(world_written=True,geometry=geometry,whole_controlled_cells_verified=len(rows),native_be_endpoints_verified=len(bes),
            original_car_rigid_translation=[0,-48,0],native_changed_groups=cap['changed_groups'],all_678_actors_unchanged=True,
            office_and_both_main_lifts_unchanged=True,playable=False,pending=['final native calls/doors/riding','final directory old-stop retirement'])
        (out/'APPLIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
        print(json.dumps(result,ensure_ascii=False),flush=True)
    except BaseException:
        if cap is not None:atomic_replace(cap['path'],cap['before'])
        if geometry is not None:
            applied=list(folder.glob('applied_*'));assert len(applied)==1
            for p in (applied[0]/'before').glob('r.*.mca'):atomic_replace(world/'dimensions/projectseele/geofront/region'/p.name,p.read_bytes())
            (applied[0]/'ROLLED_BACK.json').write_text('{"reason":"compact composite validation failed"}','utf8')
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
