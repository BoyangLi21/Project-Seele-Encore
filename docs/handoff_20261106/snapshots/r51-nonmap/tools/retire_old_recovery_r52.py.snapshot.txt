"""Retire complete R48/R50 external recovery receivers and their crew stairs.

Ownership comes from both original producer geometries, not all non-air in a
box. Earlier foundation slabs and the old compact-lift observation interface
are separately classified; this stage never clears them by material alone.
"""
import argparse,json,msvcrt
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from extend_world_depth_r52 import acquire_world_lock
from query_blocks import iter_block_entities
from pathlib import Path
import survey_r52_original_complex as survey
import extend_world_depth_r52 as extension


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--apply',action='store_true');args=p.parse_args()
    base=args.base.resolve();world=base/'WORLD';lo=(-35,-486,-17);hi=(101,-342,137)
    contract=json.loads((base/'ROOT_SPATIAL_PLAN.json').read_text('utf8'))
    assert contract['map_author']=='root' and contract['epoch']==53 and contract['delivery_scope']['id']=='scope124'
    survey.WORLD=extension.WORLD=world
    a,names=measure(lo,hi);names=list(names)
    for s in ('minecraft:air','minecraft:stone','minecraft:grass_block[snowy=false]'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)};owner=np.zeros(a.shape,bool)
    def own(b):
        x,y,z,X,Y,Z=b
        assert lo[0]<=x<=X<=hi[0] and lo[1]<=y<=Y<=hi[1] and lo[2]<=z<=Z<=hi[2],b
        owner[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]=True
    for v,cx in enumerate((-12,30,72)):
        own((cx-17,-413,-12,cx+17,-410,16))
        dz=(-13,-10,-7)[v];own((cx-15,-410,dz,cx+15,-346,dz))
        own((cx-15,-414,6,cx+15,-410,118));own((cx-17,-414,83,cx+17,-410,118))
        for xx in (cx-20,cx+18):own((xx,-480,38,xx+1,-410,119))
        for z in (20,48,80,118):own((cx-20,-414,z,cx+19,-413,z+1))
        for xx in (cx-18,cx+17):
            for z in range(-17,17):
                top=min(-414,-444+z+18);own((xx,top-2,z,xx+1,top,z))
        for z in range(17,129):
            floor=-411-(z-17)//2 if z%2 else -412-(z-18)//2
            own((cx-17,floor-2,z,cx+17,floor+1,z))
            if z in (20,36,52,68,84,100,116):
                for xx in (cx-16,cx+16):own((xx-1,-480,z-1,xx+1,floor-3,z+1))
        side=9 if v<2 else 93;edge=cx+17 if v in (0,2) else cx-17
        own((min(edge,side)-2,-413,12,max(edge,side)+2,-405,14))
        for z in range(15,35):
            floor=-411 if z<17 else -411-(z-16)//2
            own((side-2,floor-2,z,side+2,floor+1,z))
            own((side-3,floor+1,z,side+3,floor+1,z))
        target=cx+14 if v in (0,2) else cx-14
        own((min(side,target)-2,-422,34,max(side,target)+2,-420,36))
    crew_signs={(12,-407,15),(96,-407,15),(12,-416,38),(92,-416,38)}
    for q in crew_signs:own((*q,*q))
    allowed={'projectseele:nerv_structural_panel','projectseele:nerv_floor_panel','projectseele:nerv_edge_rail',
        'minecraft:polished_blackstone_stairs','minecraft:iron_block','minecraft:barrier','minecraft:oak_wall_sign'}
    selected=owner&np.isin(a,[i for i,s in enumerate(names) if s.split('[')[0] in allowed])
    before_tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    assert set(before_tags)==crew_signs
    for q,t in before_tags.items():assert str(t['id'])=='minecraft:sign' and selected[q[1]-lo[1],q[2]-lo[2],q[0]-lo[0]]
    after=a.copy();ys=np.arange(a.shape[0])[:,None,None]+lo[1]
    fill=np.broadcast_to(np.where(ys>-467,ids['minecraft:air'],np.where(ys==-467,ids['minecraft:grass_block[snowy=false]'],ids['minecraft:stone'])),a.shape)
    after[selected]=fill[selected]
    # The old approach is replaced by the three new vertical outlets; no
    # original personnel home may lose its floor/headroom during retirement.
    roster=json.loads((world/'nerv_staff_r15.json').read_text('utf8'))['stations']
    for row in roster:
        x,y,z=map(int,row['feet'])
        for yy in (y-1,y,y+1):
            if lo[0]<=x<=hi[0] and lo[1]<=yy<=hi[1] and lo[2]<=z<=hi[2]:
                assert a[yy-lo[1],z-lo[2],x-lo[0]]==after[yy-lo[1],z-lo[2],x-lo[0]],('Original personnel post changed',row['id'],x,yy,z)
    vox.WORLD=world;vox.OUT=base/'old_recovery_retirement';vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-1344,320))
    count=runs(painter,lo,a,after,names,'R52_retire_complete_original_R48_R50_recovery_receivers')
    painter.meta.update(root_author=True,producer_ownership=['prepare_underground_r48.py','prepare_geofront_airport_r50.py'],
        complete_old_receiver_retirement=True,retired_information_fixtures=[dict(pos=q,nbt=t.snbt(),reason='Original receiver crew approach retired with its entire supported platform') for q,t in before_tags.items()],
        preserve_earlier_deepslate_foundation_and_old_lift_interface_for_separate_review=True)
    folder=painter.save_plan('retired_original_external_recovery')
    report=dict(world_written=False,cells=count,retired_complete_crew_signs=4,preserve_native_train_database=True,
        remaining_separate_components=['earlier basement deck/foundation','old compact lift observation galleries','old emergency facade rim'],
        source_producer_geometry=True)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if args.apply:
        assert not list(folder.glob('applied_*'));lock=acquire_world_lock()
        try:
            report.update(world_written=True,receipt=painter.apply('retired_original_external_recovery',session_lock=lock))
            actual,palette=measure(lo,hi)
            assert np.array_equal(np.asarray([ids[s] for s in palette])[actual],after)
            assert not list(iter_block_entities(world,'projectseele:geofront',lo,hi))
            report['whole_retirement_exact_readback']=True
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
        (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
