"""Root backfill of measured, buried holes left by removed R22/R23 piers."""
import argparse
import json
import msvcrt
from pathlib import Path
import numpy as np
import regional_voxels as vox
from extend_world_depth_r52 import acquire_world_lock
from fit_original_outer_guide_slots_r52 import read_points,WORLD,sha
from query_blocks import iter_block_entities
from restore_r52_west_recorded_mountain import PROOF,OUT,TEMPLATE,vertical_runs


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    mask=PROOF/'WEST_CURRENT_RETIRED_PIER_BURIED_AIR_MASK.npz'
    evidence=PROOF/'WEST_CURRENT_SIDE_VOID_PROVENANCE.json'
    assert sha(mask)=='83628ab42d36d88ae2cd35aac9d32042bc299df34f6c20a8cb518aac3b365657'
    assert sha(evidence)=='d663213256ccb71f0d024dc092bf535feab97dd0b8b8192109f64545ef18be54'
    report=json.loads(evidence.read_text(encoding='utf8'))
    stage='backfill_verified_buried_retired_piers'
    assert not list((OUT/stage).glob('applied_*'))
    with np.load(mask,allow_pickle=False)as z:
        cells={tuple(map(int,p)):str(s)for p,s in zip(z['positions'],z['current_state'],strict=True)}
    assert len(cells)==2346 and set(cells.values())=={'minecraft:air'}
    assert min(p[1]for p in cells)==65 and max(p[1]for p in cells)==115
    clear={tuple(p)for p in json.loads(TEMPLATE.read_text(encoding='utf8'))['union_clear_cells']}
    assert not set(cells)&clear
    actual,selected=read_points(set(cells));assert actual==cells
    lo=tuple(min(p[i]for p in cells)for i in range(3));hi=tuple(max(p[i]for p in cells)for i in range(3))
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=selected));assert not set(tags)&set(cells)
    painter=vox.Painter(vertical_bounds=(-960,320))
    for box,a,b in vertical_runs({p:(s,'minecraft:stone')for p,s in cells.items()}):
        painter.exact(box,a,b,'R52_natural_backfill_of_verified_retired_pier_holes')
    locks={str(mask):sha(mask),str(evidence):sha(evidence),str(TEMPLATE):sha(TEMPLATE)}|report['source_locks']
    for p,h in locks.items():assert sha(p)==h,('Changed source',p)
    painter.meta.update(root_author=True,old_piers_recreated=False,current_rail_opening_kept=True,source_locks=locks)
    vox.WORLD,vox.OUT,vox.DIM=WORLD,OUT,'projectseele:geofront';folder=painter.save_plan(stage)
    result=dict(schema='projectseele.r52.root-retired-pier-natural-backfill.v1',world_written=False,
                changed_cells=2346,source_locks=locks,rail_opening_overlap=0,original_or_new_pier_rebuilt=False,
                retired_horizontal_unknown_air_filled=False,native_art_passed=False)
    if args.apply:
        lock=acquire_world_lock()
        try:
            now,_=read_points(set(cells));assert now==cells
            result.update(world_written=True,receipt=painter.apply(stage,session_lock=lock))
        finally:
            msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (folder/'PLAN.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items()if k not in ('source_locks','receipt')}),flush=True)


if __name__=='__main__':main()
