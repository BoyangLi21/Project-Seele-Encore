"""Root-authored serial bank civil plant, using original R50 bank sections.

This stage installs the two additional lower banks and the level transfer
halls. Vertical/inclined outlet swept volumes and live rail/gate bindings are
separate mandatory stages; the result is not a playable facility yet.
"""
import argparse,json,math,msvcrt
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE,HANGAR
from facility_frame_nbt_r52 import state_in_frame
from plan_factory_r20 import guide_y
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from extend_world_depth_r52 import acquire_world_lock
from query_blocks import iter_block_entities


def main():
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
    world=BASE/'WORLD_R52';receipt=BASE/'hangar_move/complete_hangar_incline_translation/PLAN.json'
    assert json.loads(receipt.read_text('utf8'))['world_written']
    data=np.load(BASE/'survey/original_hangar_transfer_launch.npz');a=data['states'];o=data['origin'];sp=list(map(str,data['palette']))
    lo=(-54,-680,-467);hi=(108,-546,112)
    current,cp=measure(lo,hi)
    names=list(dict.fromkeys(cp+[state_in_frame(s,HANGAR) for s in sp]+['minecraft:barrier','minecraft:air',
        'projectseele:nerv_machine_edge','projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel']))
    codes={s:i for i,s in enumerate(names)};before=np.asarray([codes[s] for s in cp],np.uint16)[current];after=before.copy()
    authored=np.zeros(before.shape,bool)
    def sl(b):
        x,y,z,X,Y,Z=b;assert lo[0]<=x<=X<=hi[0] and lo[1]<=y<=Y<=hi[1] and lo[2]<=z<=Z<=hi[2]
        return np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]
    def put(b,values):after[sl(b)]=values;authored[sl(b)]=True
    def fill(b,state):put(b,codes[state])
    remap=np.asarray([codes[state_in_frame(s,HANGAR)] for s in sp],np.uint16)
    bank=remap[a[-444-o[1]:-310-o[1]+1,-54-o[2]:-18-o[2]+1,-29-o[0]:89-o[0]+1]][:,::-1,::-1]
    for shift in (-453,-573):put((-29,-680,106+shift,89,-546,142+shift),bank)
    # Freeze an original cross-section; translate its bearing surface to a
    # level guide without changing the original trench width or shell finish.
    z=-100;g=int(math.floor(guide_y(z)))
    section=remap[a[g-6-o[1]:g+86-o[1]+1,z-o[2],:]][:,::-1]
    corridors=[(-310,105),(-430,-348)]
    for first,last in corridors:
        put((-54,-653,first,108,-561,last),np.repeat(section[:,None,:],last-first+1,axis=1))
        # Columns at regular intervals inherit the original structural finish.
        # They remain outside all three carriage trenches.
        for zz in range(first,last+1,20):
            for xx in (-53,107):fill((xx,-652,zz,xx,-562,min(last,zz+1)),'projectseele:nerv_machine_edge')
    gates=[]
    for bank_id,plane in ((1,106),(2,-347)):
        for lane,cx in enumerate((-12,30,72)):
            # Full-height port through the rear's two solid wall layers.
            # Collision remains closed until the real leaf controller opens.
            fill((cx-16,-646,plane,cx+16,-572,plane+1),'minecraft:barrier')
            for xx in (cx-17,cx+17):fill((xx,-652,plane,xx,-570,plane+1),'projectseele:nerv_machine_edge')
            fill((cx-17,-571,plane,cx+17,-570,plane+1),'projectseele:nerv_machine_edge')
            gates.append(dict(id=f'bank_{bank_id}_rear_lane_{lane}',bank=bank_id,lane=lane,
                centre=[cx+.5,-646,plane+1.0],plane_z=plane,width=33,height=75,collision_depth=2,
                leaf_mechanism='four telescoping leaves per side; each side pocket narrower than half the 9m inter-lane gap',
                closed=True,live_binding_pending=True))
    # The existing first bank is the only authored component this stage joins.
    # All other overwritten cells must be actual underground geology.
    existing=np.zeros_like(authored);existing[sl((-29,-680,106,89,-546,112))]=True
    natural={'minecraft:stone','minecraft:deepslate[axis=y]','minecraft:deepslate','minecraft:bedrock'}
    touched={names[int(v)] for v in np.unique(before[authored&~existing])}
    assert touched<=natural,('Unexpected facility in new serial-bank plant',touched-natural)
    for point,tag in iter_block_entities(world,'projectseele:geofront',lo,hi):
        x,y,z=point
        assert not authored[y-lo[1],z-lo[2],x-lo[0]],('Device in authored serial-bank plant',point,str(tag['id']))
    vox.WORLD=world;vox.OUT=BASE/'launch_banks';vox.DIM='projectseele:geofront'
    painter=vox.Painter(vertical_bounds=(-960,320));count=runs(painter,lo,before,after,names,'R52_original_style_serial_banks')
    pending=['live continuous bogie rails','new pressure leaf controllers and interlocks','all three outlet swept shafts','native geometry/visual inspection']
    painter.meta.update(root_author=True,bank_source='frozen original R50 lower launch bank',corridor_source_cross_section_z=-100,
        three_banks_three_partitioned_lanes=True,gates=gates,playable=False,pending=pending)
    folder=painter.save_plan('serial_banks_and_tracked_halls')
    report=dict(world_written=False,playable=False,changed_cells=count,bounds=[lo,hi],gates=gates,
        banks=[dict(bank=i+1,centre_z=z,foot_y=-646,lane_x=[-11.5,30.5,72.5]) for i,z in enumerate((124.5,-328.5,-448.5))],
        corridor_segments=[dict(first_z=f,last_z=l,foot_y=-646) for f,l in corridors],pending=pending)
    (folder/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='gates'},ensure_ascii=False),flush=True)
    if args.apply:
        assert not list(folder.glob('applied_*')),'Existing receipt requires inspection'
        lock=acquire_world_lock()
        try:report.update(world_written=True,receipt=painter.apply('serial_banks_and_tracked_halls',session_lock=lock))
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
        (folder/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':main()
