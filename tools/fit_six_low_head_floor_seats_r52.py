"""Six finite shallow corner recesses for the actual0262 lowered heads."""
import json, hashlib, msvcrt
from pathlib import Path
import regional_voxels as vox
from r52_spatial_plan import BASE
from query_blocks import read_box, iter_block_entities
from extend_world_depth_r52 import acquire_world_lock

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'.Codex/r52_continuous_route_migration_20261012/0262_66F5_ACTUAL_OUTER_LOADING_AND_LEGACY_BOUNDS.json'
OUT=BASE/'continuous_upright/final_0262_loading_floor';STAGE='six_shallow_nonbearing_corner_recesses'
WORLD=BASE/'WORLD_R52'

def main():
    assert not list((OUT/STAGE).glob('applied_*')), 'Do not replay'
    model=ROOT/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json'
    source=json.loads(SOURCE.read_text());assert source['model_source_sha256']==hashlib.sha256(model.read_bytes()).hexdigest()
    assert all(not r['original_six_support_cube_hits'] for r in source['original_lift_and_six_supports'])
    cells=sorted({tuple(p) for r in source['actual_outer_below_floor_geometry'] for p in r['triangle_intersected_floor_cells']})
    assert len(cells)==6 and all(p[1]==-747 for p in cells)
    minimum=min(r['actual_min_y'] for r in source['actual_outer_below_floor_geometry'])
    assert minimum>-746.5 and minimum<-746
    p=vox.Painter(vertical_bounds=(-960,320))
    for x,y,z in cells:
        data=read_box(WORLD,'projectseele:geofront',(x,y-1,z),(x,y+1,z))
        assert data[x,y,z]=='projectseele:nerv_shaft_panel' and data[x,y-1,z]=='projectseele:nerv_shaft_panel' and data[x,y+1,z]=='minecraft:air'
        assert not list(iter_block_entities(WORLD,'projectseele:geofront',(x,y-1,z),(x,y+1,z)))
        p.exact((x,y,z,x,y,z),data[x,y,z],'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]','R52_actual_low_head_shallow_floor_recess')
    vox.WORLD=WORLD;vox.OUT=OUT;vox.DIM='projectseele:geofront'
    p.meta.update(root_author=True,actual_model_sha256=source['model_source_sha256'],actual_source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  source_lowest_y=minimum,shallow_floor_top_y=-746.5,original_six_supports_each_unit_preserved=True)
    lock=acquire_world_lock()
    try:receipt=p.apply(STAGE,session_lock=lock)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    report=dict(world_written=True,cells=cells,receipt=receipt,clearance_m=minimum+746.5,original_floor_below_preserved=True,native_game_passed=False)
    (OUT/STAGE/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':main()
