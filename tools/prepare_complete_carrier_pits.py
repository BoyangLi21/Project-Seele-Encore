"""Root's three final dry carrier pits with the measured downward hatch seats."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import math
import msvcrt
import uuid
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids


ROOT=Path(__file__).resolve().parents[1]
DROP=384


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    base=a.base.resolve();world=base/'WORLD';survey.WORLD=extension.WORLD=world
    vox.WORLD=world;vox.OUT=base/'complete_carrier_pits';vox.DIM='projectseele:geofront'
    stage='three_supported_dry_carrier_pits';assert not list((vox.OUT/stage).glob('applied_*'))
    measure_path=ROOT/'.Codex/r52_airlift_draft/ACTUAL_SERVICE_DOWNWARD_HATCH_MEASUREMENT_ROOT_FRAME_MINUS678_99.json'
    measured=json.loads(measure_path.read_text('utf8'))
    assert measured['foundation_cell_intersections']==0 and not measured['whole_open_close_curve_original_columns_intersection']
    assert measured['spec_example_clocks_root_must_confirm']==dict(opening_x=33,opening_z=33,open_ticks=120,close_ticks=180,separation_sign=-1,beam_bottom=-2.01,service_column_ports=True)
    hatch_interface=ROOT/'.Codex/map_complete_20261013/route_audit/service_hatch_r53/SERVICE_HATCH_GEOMETRY_INTERFACE.json'
    hatch=json.loads(hatch_interface.read_text('utf8'))
    assert hatch['fixed_and_moving_peer_hits']==0 and hatch['hatch_bearings_24_unchanged']
    assert hatch['spec']['serviceGantryYawDegrees']==180
    assert hashlib.sha256(Path(hatch['geometry_file']).read_bytes()).hexdigest()==hatch['geometry_sha256']
    for file,digest in hatch['source_sha256'].items():assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==digest
    mask_proof=json.loads((ROOT/'.Codex/map_complete_20261013/route_audit/lower_current/ACTUAL_198_MASK_VS_ALL36_BEARINGS.json').read_text('utf8'))
    assert mask_proof['all12_lower_permanent_support_cells_preserved'] and mask_proof['all24_hatch_bearing_cells_preserved']
    assert mask_proof['actual12_lower_pad_bottom_faces_fully_supported']
    lo=(-34,-752-DROP,307);hi=(95,-678-DROP,350);before,names=survey.measure(lo,hi)
    for state in ('minecraft:air','projectseele:nerv_structural_panel','projectseele:nerv_shaft_panel'):
        if state not in names:names.append(state)
    ids={s:i for i,s in enumerate(names)};after=before.copy();owned=np.zeros(before.shape,bool)
    def fill(box,state):
        x,y,z,X,Y,Z=box;y-=DROP;Y-=DROP
        assert lo[0]<=x<=X<=hi[0] and lo[1]<=y<=Y<=hi[1] and lo[2]<=z<=Z<=hi[2]
        s=np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]
        after[s]=ids[state];owned[s]=True
    gates=[]
    for variant,cx in enumerate((72,30,-12)):
        frame=[cx+.5,-678.99-DROP,328.5]
        fill((cx-18,-751,310,cx+18,-680,346),'projectseele:nerv_shaft_panel')
        # The raised-body export measures rise0 at footY-68.014. Keep almost
        # two metres below its true low point, rather than rounding into it.
        fill((cx-16,-748,312,cx+16,-680,344),'minecraft:air')
        fill((cx-21,-685,310,cx+21,-680,346),'minecraft:air')
        for z,Z in ((309,311),(345,347)):
            fill((cx-21,-687,z,cx+21,-686,Z),'projectseele:nerv_structural_panel')
            fill((cx-21,-681,z,cx+21,-680,Z),'minecraft:air')
        supports=[]
        for local in measured['mandatory_bearing_points_local']:
            point=np.asarray(frame)+local;x,z=math.floor(point[0]),math.floor(point[2])
            assert abs(point[1]+681+DROP)<1e-7 and z in (309,347)
            fill((x,-685,z,x,-682,z),'projectseele:nerv_structural_panel')
            supports.append(dict(position=[x,-682-DROP,z],state='projectseele:nerv_structural_panel',source_contact=point.tolist()))
        cells=[]
        for x in range(cx-16,cx+17):
            for z in range(311,346):
                state=names[int(before[-679-DROP-lo[1],z-lo[2],x-lo[0]])]
                assert state.startswith('projectseele:nerv_') or state in ('minecraft:iron_block','minecraft:light_gray_concrete','minecraft:polished_basalt[axis=y]','minecraft:sea_lantern','minecraft:polished_blackstone','minecraft:lodestone')
                cells.append(dict(position=[x,-679-DROP,z],closed=state,open='minecraft:air'))
        assert len(cells)==1155
        gates.append(dict(resource=f'bay_{variant}_service_pit',variant=variant,kind='SILO',stage=0,
            visual=str(uuid.uuid5(uuid.NAMESPACE_URL,f'projectseele:complete53:bay_{variant}_service_pit')),
            frame=dict(position=frame,quaternion=[0,0,0,1]),width=33,height=33,
            silo_hatch=dict(measured['spec_example_clocks_root_must_confirm'],upright_guide_ports=False,service_gantry_yaw_degrees=180),supports=supports,cells=cells))
    pocket_path=ROOT/'.Codex/map_complete_20261013/route_audit/lower_current/ACTUAL_CURRENT_LOWER_RECESSES_R53.json'
    pocket=json.loads(pocket_path.read_text('utf8'))
    assert hashlib.sha256((ROOT/'src/main/resources/assets/projectseele/mesh/cage_lower_telescopes_r52.json').read_bytes()).hexdigest()==pocket['source_sha']
    recesses=[r for unit in pocket['units'] for r in unit['cells']]
    for row in recesses:
        x,y,z=row['position'];iy,iz,ix=y-lo[1],z-lo[2],x-lo[0]
        assert 0<=iy<after.shape[0] and 0<=iz<after.shape[1] and 0<=ix<after.shape[2]
        assert names[int(before[iy,iz,ix])]==row['before_world'],'Current lower recess source changed'
        assert owned[iy,iz,ix] and names[int(after[iy,iz,ix])]==row['state'],('Unowned or changed exact lower-frame recess',row)
        after[iy,iz,ix]=ids['minecraft:air']
    assert np.array_equal(before[-679-DROP-lo[1]:],after[-679-DROP-lo[1]:]),'Original wet floor and LCL remain intact until native draining'
    changed=before!=after
    allowed={'minecraft:air','minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]','minecraft:bedrock','minecraft:sea_lantern'}
    actual={names[int(v)] for v in np.unique(before[changed])}
    assert all(s in allowed or s.startswith('projectseele:nerv_') for s in actual),('Unknown service pit occupant',actual)
    for (x,y,z),tag in iter_block_entities(world,vox.DIM,lo,hi):assert not changed[y-lo[1],z-lo[2],x-lo[0]],('Original device in pit excavation',x,y,z,str(tag['id']))
    painter=vox.Painter(vertical_bounds=(-1344,320));count=cuboids(painter,lo,before,after,names,'current_complete_dry_carrier_pit_and_measured_hatch_seats')
    painter.meta.update(root_author=True,original_wet_floor_preserved=True,lower_machine_source=pocket['source_sha'],playable=False)
    folder=painter.save_plan(stage)
    for gate in gates:
        raw=gzip.compress(json.dumps([gate.pop('cells')],separators=(',',':')).encode(),mtime=0)
        name=gate['resource']+'_cells.json.gz';(folder/name).write_bytes(raw)
        gate['collision_steps']=dict(cells_file=name,sha256=hashlib.sha256(raw).hexdigest())
    report=dict(world_written=False,playable=False,changed_cells=count,gates=gates,bounds=[lo,hi],
        exact_lower_frame_recesses=len(recesses),rise0_bottom_clearance_m=1.986,terminal_roof_separation_m=45,
        original_floor_and_wet_geometry_identical=True,hatch_source_sha=measured['source_sha'],
        selected_actual_hatch_geometry_sha256=hatch['geometry_sha256'],service_gantry_yaw_degrees=180,
        net_aperture=[33,33],actual_dynamic_collision_extent=[33,35],dynamic_floor_cells=3465,
        hatch_measurement_sha256=hashlib.sha256(measure_path.read_bytes()).hexdigest(),
        pending=['all current actual fixed/moving source to civil checks','native wet drain/raise/unclamp and reverse cycle'])
    np.savez_compressed(folder/'EXACT_BEFORE_AFTER.npz',origin=lo,palette=names,before=before,after=after,positive_edit_mask=changed)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='gates'}),flush=True)
    if a.apply:
        lock=extension.acquire_world_lock()
        try:
            report['receipt']=painter.apply(stage,session_lock=lock)
            current,pal=survey.measure(lo,hi);assert np.array_equal(np.asarray([ids[s] for s in pal],np.uint16)[current],after)
            report.update(world_written=True,whole_component_exact_readback=True)
            (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
