"""Align the closed proxy to the installed, measured south-door leaf plane."""
import argparse,json,msvcrt
from pathlib import Path
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'air_transport_shaft/south_leaf_collision_alignment'
    assert not (out/'APPLIED.json').exists()
    source=json.loads((base/'air_transport_shaft/actual_machine_bearings_and_cassettes/PLAN.json').read_text('utf8'))
    gate=next(c for c in source['cases'] if c['kind']=='vertical')
    assert source['world_written'] and gate['frame']==[-1120,-475,-635]
    geometry=json.loads((Path(__file__).resolve().parents[1]/'.Codex/r52_airlift_draft/ACTUAL_VERTICAL_SIDE_STACK_MEASUREMENT.json').read_text('utf8'))
    case=next(c for c in geometry['cases'] if c['net_width_height']==[164.,181.])
    leaves=[c for c in case['actual_part_samples'] if c['moving'] and c['progress']==0]
    assert len(leaves)==8 and all(c['bounds'][2]==0 and .979<c['bounds'][5]<.981 for c in leaves)
    vox.WORLD=survey.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront'
    lo=(-1202,-475,-637);hi=(-1039,-295,-635);before,names=survey.measure(lo,hi)
    air=names.index('minecraft:air');barrier=names.index('minecraft:barrier')
    assert np.all(before[:,:2,:]==barrier) and np.all(before[:,2,:]==air)
    assert not list(iter_block_entities(world,vox.DIM,lo,hi))
    after=before.copy();after[:,:2,:]=air;after[:,2,:]=barrier
    painter=vox.Painter(vertical_bounds=(-1344,320));count=cuboids(painter,lo,before,after,names,'actual_south_door_closed_leaf_alignment')
    painter.meta.update(root_author=True,actual_closed_local_z=[0,.9800000190734863],supports_unchanged=True)
    painter.save_plan('align_measured_south_leaf')
    if not a.apply:return
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('align_measured_south_leaf',session_lock=lock)
        current,palette=survey.measure(lo,hi);assert np.array_equal(np.array([names.index(s) for s in palette])[current],after)
        report=dict(world_written=True,changed_cells=count,closed_box=[-1202,-475,-635,-1039,-295,-635],
                    old_two_planes_retired=True,actual_machine_frame=gate['frame'],receipt=receipt)
        (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
