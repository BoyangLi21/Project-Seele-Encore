"""Close the unused terminal-bank rear apertures as explicit static end walls."""
import argparse,json,msvcrt
from pathlib import Path
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension
from query_blocks import iter_block_entities


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'bank3_unused_rear_retirement';assert not(out/'APPLIED.json').exists()
    directory=json.loads((base/'phased_routes/PHASED_MONOTONE_DESIGN.json').read_text('utf8'))
    assert not any(r['id'].startswith('bank_3_rear') for r in directory['resources'])
    vox.WORLD=survey.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-1344,320));boxes=[]
    for cx in (-12,30,72):
        lo=(cx-16,-1030,10);hi=(cx+16,-956,11);before,palette=survey.measure(lo,hi)
        assert np.all(before==palette.index('minecraft:barrier'))
        assert not list(iter_block_entities(world,vox.DIM,lo,hi))
        painter.exact((*lo,*hi),'minecraft:barrier','projectseele:nerv_shaft_panel','retired_unused_bank3_rear_static_end_wall')
        boxes.append([lo,hi])
    painter.meta.update(root_author=True,bank3_vertical_ascent_unchanged=True,unused_rear_controllers_not_installed=True)
    painter.save_plan('retire_three_unclaimed_rear_seals')
    if not a.apply:return
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('retire_three_unclaimed_rear_seals',session_lock=lock)
        for lo,hi in boxes:
            actual,palette=survey.measure(lo,hi);assert np.all(actual==palette.index('projectseele:nerv_shaft_panel'))
        report=dict(world_written=True,changed_cells=14850,unused_rear_gates_retired=3,static_end_walls=True,receipt=receipt)
        (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
