"""Extend bank two straight to its measured GeoFront ground, original style.

The actual three 33m internal shaft sections remain unchanged. Three 31m
surface seals stay physically closed pending their real runtime controllers.
"""
import argparse,json,uuid
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE,HANGAR
from facility_frame_nbt_r52 import state_in_frame
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities
from survey_r52_original_complex import measure


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';out=BASE/'bank2_vertical_outlet';frozen=np.load(out/'SOURCE.npz')
    lo=tuple(map(int,frozen['origin']));a=frozen['states'];hi=(lo[0]+a.shape[2]-1,lo[1]+a.shape[0]-1,lo[2]+a.shape[1]-1)
    source=np.load(BASE/'survey/original_hangar_transfer_launch.npz');o=source['origin'];sp=list(map(str,source['palette']))
    names=list(dict.fromkeys(list(map(str,frozen['palette']))+[state_in_frame(s,HANGAR)for s in sp]+[
        'minecraft:barrier','minecraft:air','projectseele:nerv_floor_panel','projectseele:nerv_structural_panel','projectseele:nerv_machine_edge']))
    ids={s:i for i,s in enumerate(names)};before=np.asarray([ids[str(s)]for s in frozen['palette']],np.uint16)[a];after=before.copy();owned=np.zeros(a.shape,bool)
    def sl(b):
        x,y,z,X,Y,Z=b;assert lo[0]<=x<=X<=hi[0] and lo[1]<=y<=Y<=hi[1] and lo[2]<=z<=Z<=hi[2]
        return np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]
    def put(b,value):after[sl(b)]=value;owned[sl(b)]=True
    def fill(b,state):put(b,ids[state])
    # The real grass datum is -476/-477 here. The apron has at most a two-metre
    # exposed edge and meets the existing meadow, not the unrelated -467 datum.
    fill((-34,-478,-352,96,-477,-305),'projectseele:nerv_structural_panel')
    fill((-34,-476,-352,96,-476,-305),'projectseele:nerv_floor_panel')
    fill((-34,-475,-352,96,-408,-305),'minecraft:air')
    remap=np.asarray([ids[state_in_frame(s,HANGAR)]for s in sp],np.uint16)
    section=remap[source['states'][-318-o[1],-54-o[2]:-17-o[2],-29-o[0]:90-o[0]]][::-1,::-1]
    assert section.shape==(37,119)
    put((-29,-545,-347,89,-477,-311),np.repeat(section[None,:,:],69,axis=0))
    # Keep the copied original lower shaft endpoint as a strict connection;
    # it is a separate already-built component, never silently repainted.
    bottom=before[-546-lo[1],-347-lo[2]:-310-lo[2],-29-lo[0]:90-lo[0]]
    base_names={names[int(v)]for v in np.unique(bottom)}
    assert base_names<={'minecraft:air','projectseele:nerv_shaft_panel','projectseele:nerv_wall_panel','minecraft:black_concrete','minecraft:iron_block','projectseele:nerv_machine_edge','projectseele:nerv_structural_panel'},base_names
    seals=[]
    for lane,cx in enumerate((-12,30,72)):
        cz=-329;plane=-476
        fill((cx-15,plane,cz-15,cx+15,plane,cz+15),'minecraft:barrier')
        for x in (cx-17,cx+17):fill((x,plane,cz-17,x,plane,cz+17),'projectseele:nerv_machine_edge')
        for z in (cz-17,cz+17):fill((cx-17,plane,z,cx+17,plane,z),'projectseele:nerv_machine_edge')
        seals.append(dict(id=f'bank_2_surface_lane_{lane}',lane=lane,variant=2-lane,
            visual_uuid=str(uuid.uuid5(uuid.NAMESPACE_URL,f'projectseele:r52:bank2:surface:{lane}')),
            visual_type='projectseele:nerv_silo_door',visual_position=[cx+.5,plane+.01,cz+.5],
            closed_collision_box=[cx-15,plane,cz-15,cx+15,plane,cz+15],closed_state='minecraft:barrier',open_state='minecraft:air',
            original_model='TvFacilityMeshes.shaftHatch',width=31,depth=31,body_root_exit=[cx+.5,-475,cz+.5],
            actual_foot_frame_pending_source_sole_binding=True,controller_commissioned=False))
    # Above the existing bank all admitted source is measured natural geology
    # and empty meadow. No old room, device, tree or railway may be overwritten.
    original_component=np.zeros_like(owned);original_component[sl((-29,-546,-347,89,-546,-311))]=True
    touched={names[int(v)]for v in np.unique(before[owned&~original_component])}
    assert touched<={'minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'},touched
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));assert not tags,tags
    actual,palette=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in palette],np.uint16)[actual],before),'Measured outlet source changed'
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
    count=runs(p,lo,before,after,names,'R52_bank2_original_style_vertical_outlet')
    p.meta.update(root_author=True,vertical_only=True,original_section_y=-318,bank=2,geo_ground_measured=True,
        apron_block_y=-476,body_root_y=-475,seals=seals,playable=False,actual_carrier_bounds_receipt='.Codex/r52_full_assembly_geometry/RAISED_CARRIER_AND_ASSEMBLY_BOUNDS.json')
    plan=p.save_plan('bank2_vertical_GeoFront_exit')
    report=dict(world_written=False,playable=False,changed_cells=count,shaft_top=-477,ground_seal_y=-476,exit_body_root_y=-475,
        preserved_existing_bank_bottom=True,original_three_lane_cross_section=True,seals=seals,
        pending=['actual door controller and physical opening interlock','continuous guide/support commissioning','native whole assembly vertical transit and emergence'])
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items()if k!='seals'}),flush=True)
    if args.apply:
        assert not list(plan.glob('applied_*')),'Applied outlet stage must not be replayed'
        receipt=p.apply('bank2_vertical_GeoFront_exit')
        actual,palette=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in palette],np.uint16)[actual],after)
        report.update(world_written=True,receipt=receipt,whole_outlet_exact_readback=True)
        (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
