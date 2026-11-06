"""Move only added hatch bearings clear of the measured downward leaf stroke."""
import json,math,hashlib
from pathlib import Path
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities

root=Path(__file__).resolve().parents[1];out=BASE/'carrier_service_pits';stage='downward_hatch_outer_bearing_correction'
assert not list((out/stage).glob('applied_*'))
old=json.loads((out/'three_dry_pits_below_original_wet_floors/PLAN.json').read_text('utf8'));assert old['world_written']
src=root/'.Codex/r52_airlift_draft/ACTUAL_SERVICE_DOWNWARD_HATCH_MEASUREMENT_ROOT_FRAME_MINUS678_99.json';g=json.loads(src.read_text())
lo=(-34,-687,308);hi=(95,-679,348);before,names=measure(lo,hi)
for s in ('minecraft:air','projectseele:nerv_structural_panel'):
    if s not in names:names.append(s)
ids={s:i for i,s in enumerate(names)};after=before.copy()
def fill(x,y,z,X,Y,Z,s):after[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]=ids[s]
gates=[]
for gate in old['gates']:
    cx=int(math.floor(gate['frame'][0]));support=[]
    for cell in gate['support_cells']:
        x,y,z=cell['position'];assert z in(311,345)
        assert all(names[int(before[yy-lo[1],z-lo[2],x-lo[0]])]=='projectseele:nerv_structural_panel'for yy in range(-685,-681))
        fill(x,-685,z,x,-682,z,'minecraft:air')
    for z,Z in ((309,311),(345,347)):
        fill(cx-21,-687,z,cx+21,-686,Z,'projectseele:nerv_structural_panel')
        fill(cx-21,-681,z,cx+21,-680,Z,'minecraft:air')
    for p in g['mandatory_bearing_points_local']:
        xyz=np.array(p)+gate['frame'];x,y,z=math.floor(xyz[0]),round(xyz[1])-1,math.floor(xyz[2]);assert y==-682 and z in(309,347)
        fill(x,-685,z,x,-682,z,'projectseele:nerv_structural_panel')
        support.append(dict(position=[x,y,z],state='projectseele:nerv_structural_panel',source_contact=xyz.tolist()))
    gates.append(dict(id=gate['id'],frame=gate['frame'],support_cells=support))
assert np.array_equal(before[-679-lo[1]],after[-679-lo[1]])
assert not list(iter_block_entities(BASE/'WORLD_R52','projectseele:geofront',lo,hi))
vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
n=runs(p,lo,before,after,names,'R52_real_downward_leaf_clear_bearings');p.meta.update(root_author=True,original_wet_floor_unchanged=True,gates=gates)
plan=p.save_plan(stage);receipt=p.apply(stage);actual,pal=measure(lo,hi);assert np.array_equal(np.array([ids[s]for s in pal],np.uint16)[actual],after)
(plan/'PLAN.json').write_text(json.dumps(dict(world_written=True,changed_cells=n,receipt=receipt,gates=gates,geometry_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),whole_component_exact_readback=True,native_door_cycle_pending=True),indent=2),'utf8')
