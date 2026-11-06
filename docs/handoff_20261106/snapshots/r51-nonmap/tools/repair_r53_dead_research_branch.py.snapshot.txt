"""Retire the reported buried research approach; keep the upper working bridge.

The lower branch has no destination after the original HQ translation. Restore
the adjacent measured pyramid shell and close its opening at the retained hall.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids
from model_r53_facility import export
from verify_main_r20 import entities
from prepare_mtr_member_patch_r52 import Parser

LO,HI=(92,-560,393),(152,-547,405)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--world',type=Path)
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args();base=args.base.resolve();world=(args.world or base/'CANDIDATE').resolve()
    assert world in ((base/'CANDIDATE').resolve(),(base/'server/SEELE_R53_ACCESS_TEST').resolve())
    out=base/'dead-research-branch';out.mkdir(exist_ok=True)
    plan=out/'EXACT_PROPOSAL.npz'
    def idx(p):x,y,z=p;return y-LO[1],z-LO[2],x-LO[0]
    if not args.apply:
        assert not plan.exists(),'Keep the original proposal; do not regenerate after installation'
        survey.WORLD=world;before,palette=survey.measure(LO,HI);after=before.copy()
        tags=dict(iter_block_entities(world,survey.DIM,LO,HI))
        for y in range(-558,-547):
            for x in range(95,151):
                fabric=palette[int(before[idx((x,y,394))])]
                assert fabric in ('minecraft:air','minecraft:stone','projectseele:nerv_pyramid_panel')
                for z in range(395,404):after[idx((x,y,z))]=palette.index(fabric)
        for state in ('projectseele:nerv_structural_panel','projectseele:nerv_wall_panel','projectseele:clear_glass'):
            if state not in palette:palette.append(state)
        for y in range(-554,-548):
            for z in range(395,404):
                material='projectseele:nerv_structural_panel' if y==-549 or z in (395,403) else 'projectseele:nerv_wall_panel'
                if -553<=y<=-551 and 397<=z<=401:material='projectseele:clear_glass'
                after[idx((94,y,z))]=palette.index(material)
        mask=before!=after
        assert all(not mask[idx(p)] for p in tags),'Retain all devices in the adjoining hall'
        for z in range(396,403):
            for y in (-554,-553):
                assert palette[int(before[idx((121,y,z))])]=='minecraft:air'
                assert palette[int(before[idx((150,y,z))])]=='minecraft:stone'
            assert palette[int(before[idx((94,-556,z))])]=='projectseele:nerv_structural_panel'
        survey.WORLD=base/'WORLD';frozen,names=survey.measure(LO,HI)
        assert np.array_equal(np.asarray(names)[frozen][mask],np.asarray(palette)[before][mask])
        np.savez_compressed(plan,origin=LO,palette=palette,before=before,after=after,positive_edit_mask=mask)
        export(before,palette,LO,HI,out,'before');export(after,palette,LO,HI,out,'after')
        report=dict(world_written=False,complaint=[121,-555,399],changed_cells=int(mask.sum()),
                    seven_lane_frozen_dead_end_detected=True,original_complete_pyramid_base_y=-559,
                    retained_hall_west_of_x94=True,upper_working_research_bridge_unchanged=True,
                    retained_adjacent_block_entities=len(tags),new_shell_uses_measured_adjacent_north_profile=True,
                    pending=['Current actor/rail protection','Native hall and actual visual review'])
        (out/'REVIEW.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report));return
    with np.load(plan) as d:before=d['before'];after=d['after'];palette=d['palette'].tolist();mask=d['positive_edit_mask']
    survey.WORLD=world;actual,names=survey.measure(LO,HI)
    remap=np.asarray([palette.index(s) if s in palette else 65535 for s in names],np.uint16)
    assert np.array_equal(remap[actual][mask],before[mask]),'Exact source states changed'
    tags=dict(iter_block_entities(world,survey.DIM,LO,HI));assert all(not mask[idx(p)] for p in tags)
    for actor in entities(world).values():
        p=list(map(float,actor['Pos']))
        assert not(93<=p[0]<=151 and -560<=p[1]<=-547 and 394<=p[2]<=404),'Retain actor and its standing place'
    assert (out/'RAIL_PROTECTION.json').is_file(),'Review native rail geometry before installation'
    rail=json.loads((out/'RAIL_PROTECTION.json').read_text('utf8'));assert rail['new_solid_rail_conflicts']==0
    for record in json.loads((out/'NATIVE_RAIL_INPUT.json').read_text('utf8'))['segments']:
        source=world/'mtr/projectseele/geofront/rails'/record['source']
        assert Parser(source.read_bytes()).node().value==record['source_native'],'Current native rail geometry changed'
    vox.WORLD=world;vox.DIM=survey.DIM;vox.OUT=out/world.name
    painter=vox.Painter(vertical_bounds=(-1344,320));cuboids(painter,LO,before,after,palette,'retired_buried_research_branch')
    painter.meta.update(player_entity_traffic_and_task_data_unchanged=True,upper_research_bridge_unchanged=True,
                        exact_frozen_negative_detected=True,actual_visual_review_pending=True)
    folder=painter.save_plan('retire_dead_lower_research_branch');assert not list(folder.glob('applied_*'))
    painter.apply('retire_dead_lower_research_branch')
    observed,states=survey.measure(LO,HI);expected=remap[actual];expected[mask]=after[mask]
    assert np.array_equal(np.asarray([palette.index(s) if s in palette else 65535 for s in states],np.uint16)[observed],expected)
    assert {p:t.snbt() for p,t in iter_block_entities(world,survey.DIM,LO,HI)}=={p:t.snbt() for p,t in tags.items()}
    report=dict(world=str(world),changed_cells=int(mask.sum()),whole_volume_readback=True,devices_unchanged=True)
    (vox.OUT/'INSTALLED.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report))


if __name__=='__main__':main()
