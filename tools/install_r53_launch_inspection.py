"""Apply the reviewed exact inspection-room proposal to an offline R53 copy."""
from pathlib import Path
import argparse
import json
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--world',type=Path,required=True)
    args=ap.parse_args();base=args.base.resolve();world=args.world.resolve()
    assert world in ((base/'CANDIDATE').resolve(),(base/'server/SEELE_R53_ACCESS_TEST').resolve())
    source=base/'launch-inspection-proposal'
    report=json.loads((source/'REVIEW.json').read_text('utf8'))
    assert not report['walk_failures'] and not report['new_solid_motion_core_overlap'] and report['native_device_changes']==0
    with np.load(source/'PROPOSAL.npz') as data:
        lo=tuple(map(int,data['origin']));palette=data['palette'].tolist()
        before=data['before'];after=data['after'];mask=data['positive_edit_mask']
    hi=tuple(int(lo[k]+before.shape[(2,0,1)[k]]-1) for k in range(3))
    survey.WORLD=world;actual,names=survey.measure(lo,hi)
    remap=np.asarray([palette.index(s) if s in palette else 65535 for s in names],np.uint16)
    mapped=remap[actual]
    assert np.array_equal(mapped[mask],before[mask]),'Exact installation precondition changed'
    tags=dict(iter_block_entities(world,survey.DIM,lo,hi))
    for x,y,z in tags:assert not mask[y-lo[1],z-lo[2],x-lo[0]],'Native device in edit mask'
    vox.WORLD=world;vox.DIM=survey.DIM;vox.OUT=base/'launch-inspection-install'/world.name
    painter=vox.Painter(vertical_bounds=(-1344,320))
    cuboids(painter,lo,before,after,palette,'three_launch_bank_sealed_inspection_interfaces')
    painter.meta.update(source_proposal=str(source),whole_floor_cells=report['walk_cells'],
                        native_device_changes=0,full_low_motion_core_conflicts=0,
                        original_player_entity_task_and_transport_progress_unchanged=True,
                        native_visual_acceptance_pending=True)
    folder=painter.save_plan('three_bank_inspection_rooms')
    assert not list(folder.glob('applied_*')),'Already installed; do not replay'
    painter.apply('three_bank_inspection_rooms')
    observed,states=survey.measure(lo,hi)
    lookup=np.asarray([palette.index(s) if s in palette else 65535 for s in states],np.uint16)
    expected=mapped.copy();expected[mask]=after[mask]
    assert np.array_equal(lookup[observed],expected),'Full volume readback mismatch'
    current=dict(iter_block_entities(world,survey.DIM,lo,hi))
    assert {p:t.snbt() for p,t in tags.items()}=={p:t.snbt() for p,t in current.items()},'Native block entity state changed'
    result=dict(world=str(world),changed_cells=int(mask.sum()),whole_volume_readback=True,all_block_entity_nbt_unchanged=True)
    (vox.OUT/'INSTALLED.json').write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps(result))


if __name__=='__main__':main()
