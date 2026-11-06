"""Root's current three-bank base, measured against the construction world.

The source chamber and inclined transfer are retained. Two copies sit 48 m
apart with 11 m connecting halls. Bank roles are explicit and are independent
of historical R52 numbering. This construction stage does not commission it.
"""
from pathlib import Path
import argparse
import json
import msvcrt
import numpy as np
import regional_voxels as vox
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension
from facility_frame_nbt_r52 import state_in_frame
from r52_spatial_plan import HANGAR
from plan_factory_r20 import guide_y
from prepare_continuous_upright_civil_r52 import cuboids
from query_blocks import iter_block_entities


CENTRES=(124.5,76.5,28.5)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args()
    base=args.base.resolve();world=base/'WORLD'
    assert json.loads((base/'hangar_move/complete_hangar_incline_translation/PLAN.json').read_text('utf8'))['world_written']
    survey.WORLD=extension.WORLD=world
    vox.WORLD=world;vox.OUT=base/'compact_banks';vox.DIM='projectseele:geofront'
    stage='three_compact_original_style_banks'
    assert not list((vox.OUT/stage).glob('applied_*'))
    data=np.load(base/'survey/original_hangar_transfer_launch.npz')
    a=data['states'];o=data['origin'];sp=list(map(str,data['palette']))
    lo=(-54,-680,9);hi=(108,-546,112)
    current,cp=survey.measure(lo,hi)
    names=list(dict.fromkeys(cp+[state_in_frame(s,HANGAR) for s in sp]+[
        'minecraft:air','minecraft:barrier','projectseele:nerv_machine_edge']))
    ids={s:i for i,s in enumerate(names)}
    before=np.asarray([ids[s] for s in cp],np.uint16)[current]
    after=before.copy();owned=np.zeros(before.shape,bool)
    def sl(b):
        x,y,z,X,Y,Z=b
        assert lo[0]<=x<=X<=hi[0] and lo[1]<=y<=Y<=hi[1] and lo[2]<=z<=Z<=hi[2]
        return np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]
    def put(box,value):
        after[sl(box)]=value;owned[sl(box)]=True
    rotated=np.asarray([ids[state_in_frame(s,HANGAR)] for s in sp],np.uint16)
    chamber=rotated[a[-444-o[1]:-310-o[1]+1,-54-o[2]:-18-o[2]+1,-29-o[0]:89-o[0]+1]][:,::-1,::-1]
    assert chamber.shape==(135,37,119)
    for z in (58,10):
        put((-29,-680,z,89,-546,z+36),chamber)
    section_z=-100;floor=int(np.floor(guide_y(section_z)))
    section=rotated[a[floor-6-o[1]:floor+86-o[1]+1,section_z-o[2],:]][:,::-1]
    assert section.shape==(93,163)
    for low,high in ((95,105),(47,57)):
        put((-54,-653,low,108,-561,high),np.repeat(section[:,None,:],high-low+1,axis=1))
    gates=[]
    for bank,z in ((1,106),(2,58),(3,10)):
        for lane,cx in enumerate((-12,30,72)):
            put((cx-16,-646,z,cx+16,-572,z+1),ids['minecraft:barrier'])
            for x in (cx-17,cx+17):
                put((x,-652,z,x,-570,z+1),ids['projectseele:nerv_machine_edge'])
            put((cx-17,-571,z,cx+17,-570,z+1),ids['projectseele:nerv_machine_edge'])
            gates.append(dict(id=f'bank_{bank}_rear_lane_{lane}',bank=bank,lane=lane,
                variant=2-lane,centre=[cx+.5,-646,z+1.],plane_z=z,width=33,height=75,
                closed_box=[cx-16,-646,z,cx+16,-572,z+1],closed_state='minecraft:barrier',
                open_state='minecraft:air',mechanism='telescoping_side_leaves',
                state='closed',native_binding_pending=True))
    existing=np.zeros_like(owned)
    existing[sl((-29,-680,105,89,-546,112))]=True
    natural={'minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]','minecraft:bedrock'}
    touched={names[int(v)] for v in np.unique(before[owned&~existing])}
    assert touched<=natural,('Unrelated component in current compact-bank footprint',touched-natural)
    # The old bank's third ghost rear plane is replaced by the corridor and
    # this explicitly controlled two-plane gate, with exact inverse cells.
    for pos,tag in iter_block_entities(world,vox.DIM,lo,hi):
        x,y,z=pos
        assert not owned[y-lo[1],z-lo[2],x-lo[0]],('Original device in bank patch',pos,str(tag['id']))
    painter=vox.Painter(vertical_bounds=(-960,320))
    changed=cuboids(painter,lo,before,after,names,'current_compact_three_bank_component')
    report=dict(world_written=False,playable=False,source='frozen original bank geometry',
        bank_roles=[dict(bank=1,intent='geofront'),dict(bank=2,intent='surface'),dict(bank=3,intent='hakone')],
        bank_centres_z=CENTRES,centre_spacing=48,chamber_depth=37,connector_length=11,
        lane_centres_x=[-11.5,30.5,72.5],foot_y=-646,gates=gates,changed_cells=changed,
        bounds=[lo,hi],pending=['full fixed-rail and gate sweep installation',
        'continuous nine-way outlet civil','native controls','actual visual review'])
    painter.meta.update(report,root_author=True)
    folder=painter.save_plan(stage)
    np.savez_compressed(folder/'EXACT_BEFORE_AFTER.npz',origin=lo,palette=names,before=before,after=after,positive_edit_mask=before!=after)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='gates'}),flush=True)
    if args.apply:
        lock=extension.acquire_world_lock()
        try:
            report['receipt']=painter.apply(stage,session_lock=lock)
            actual,palette=survey.measure(lo,hi)
            assert np.array_equal(np.asarray([ids[s] for s in palette],np.uint16)[actual],after)
            report.update(world_written=True,full_component_exact_readback=True)
            (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
        finally:
            msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':
    main()
