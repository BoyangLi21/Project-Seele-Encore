"""Install the measured three-well shell with complete local readback."""
from pathlib import Path
import argparse
import json
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids
from plan_r53_old_well_enclosure import escapes,LO,HI


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base',type=Path,required=True);ap.add_argument('--world',type=Path,required=True)
    args=ap.parse_args();b=args.base.resolve();w=args.world.resolve()
    assert w in ((b/'CANDIDATE').resolve(),(b/'server/SEELE_R53_ACCESS_TEST').resolve())
    source=b/'old-well-shell-preview';review=json.loads((source/'REVIEW.json').read_text('utf8'))
    assert review['after_leaking_slices']==0 and review['original_frozen_leaking_slices']>0 and review['mechanical_core_conflicts']==0
    assert len(review['retained_base_opening_spans'])==2 and review['all_changed_cells_equal_original_delivered_save']
    with np.load(source/'PREVIEW.npz') as d:
        before=d['before'];after=d['after'];mask=d['positive_edit_mask'];palette=d['palette'].tolist();core=d['core']
    survey.WORLD=w;actual,names=survey.measure(LO,HI)
    remap=np.asarray([palette.index(s) if s in palette else 65535 for s in names],np.uint16);actual=remap[actual]
    assert np.array_equal(actual[mask],before[mask]),'Exact source precondition changed'
    tags=dict(iter_block_entities(w,survey.DIM,LO,HI))
    for x,y,z in tags:assert not mask[y-LO[1],z-LO[2],x-LO[0]]
    vox.WORLD=w;vox.DIM=survey.DIM;vox.OUT=b/'old-well-shell-install'/w.name
    painter=vox.Painter(vertical_bounds=(-1344,320));cuboids(painter,LO,before,after,palette,'three_retained_active_well_shells')
    painter.meta.update(original_frozen_leak_detection=review['original_frozen_leaking_slices'],
                        native_lift_and_complete_motion_core_preserved=True,retained_base_opening_spans=review['retained_base_opening_spans'],
                        no_existing_blocks_removed=True,player_entity_task_and_traffic_data_unchanged=True,native_visual_review_pending=True)
    plan=painter.save_plan('three_retained_well_shells');assert not list(plan.glob('applied_*'))
    painter.apply('three_retained_well_shells')
    observed,states=survey.measure(LO,HI)
    lookup=np.asarray([palette.index(s) if s in palette else 65535 for s in states],np.uint16)
    expected=actual.copy();expected[mask]=after[mask]
    assert np.array_equal(lookup[observed],expected),'Whole volume readback mismatch'
    now=dict(iter_block_entities(w,survey.DIM,LO,HI));assert {p:t.snbt() for p,t in now.items()}=={p:t.snbt() for p,t in tags.items()}
    assert not any(r['horizontal_escape'] for r in escapes(observed,states,core))
    result=dict(world=str(w),added_cells=int(mask.sum()),whole_volume_readback=True,native_devices_unchanged=True,horizontal_leaking_slices=0)
    (vox.OUT/'INSTALLED.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(result))


if __name__=='__main__':main()
