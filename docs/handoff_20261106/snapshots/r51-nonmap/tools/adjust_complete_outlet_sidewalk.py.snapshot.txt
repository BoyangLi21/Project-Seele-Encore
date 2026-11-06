"""Move the proven cassette/sidewalk overlap into the adjacent same-level paving."""
import argparse,json,hashlib,msvcrt
from pathlib import Path
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'horizontal_launch_hatches/west_sidewalk';assert not(out/'APPLIED.json').exists()
    parent=json.loads((base/'horizontal_launch_hatches/APPLIED.json').read_text('utf8'))
    old=[tuple(q) for q in parent['original_sidewalk_half_slabs_retained']];assert len(old)==22
    lo=(-39,-469,131);hi=(-29,-465,144)
    vox.WORLD=survey.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront'
    before,names=survey.measure(lo,hi)
    for s in ('minecraft:air','minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'):
        if s not in names:names.append(s)
    after=before.copy();air=names.index('minecraft:air');slab=names.index('minecraft:smooth_stone_slab[type=bottom,waterlogged=false]')
    def at(q):x,y,z=q;return y-lo[1],z-lo[2],x-lo[0]
    for q in old:assert before[at(q)]==slab;after[at(q)]=air
    additions=[]
    # Existing road already has the same Y=-467 slab throughout this bend.
    # Widen nine cells on its west side; preserve five clear columns through
    # the constricted rows and rejoin the full old width at Z143.
    for z in range(131,143):
        for x in range(-38,-33):
            q=(x,-467,z);state=names[int(before[at(q)])]
            if state!=names[slab]:
                assert state in ('minecraft:grass_block[snowy=false]','minecraft:dirt','minecraft:stone'),(q,state)
                below=names[int(before[at((x,-468,z))])]
                assert below in ('minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]') or below.startswith('projectseele:nerv_'),(q,'unfounded',below)
                after[at(q)]=slab;additions.append(q)
    assert len(additions)==9,('Expected exact nine-cell paving continuation',additions)
    assert not list(iter_block_entities(world,vox.DIM,lo,hi))
    for z in range(131,143):assert all(after[at((x,-467,z))]==slab for x in range(-38,-33))
    assert all(after[at((x,-467,143))]==slab for x in range(-35,-28))
    painter=vox.Painter(vertical_bounds=(-1344,320));count=cuboids(painter,lo,before,after,names,'same_level_road_edge_around_real_gate_cassette')
    painter.meta.update(root_author=True,original_sidewalk_foot_y=-466.5,minimum_clear_width=5,existing_road_only=True,
                        actual_collision_evidence='.Codex/map_complete_20261013/route_audit/prelaunch_slots_candidate/slabs/GATE14_CURRENT_WORLD_HITS.json')
    painter.save_plan('west_outlet_sidewalk_continuity')
    if not a.apply:return
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('west_outlet_sidewalk_continuity',session_lock=lock)
        actual,palette=survey.measure(lo,hi);assert np.array_equal(np.asarray([names.index(s) for s in palette])[actual],after)
        report=dict(world_written=True,changed_cells=count,retired_overlap_cells=22,added_paving_cells=9,
                    original_paving_datum_preserved=True,clear_width=5,whole_readback=True,receipt=receipt)
        (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
