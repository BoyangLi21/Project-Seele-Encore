"""Root's single west-face reservoir and restoration of the former lake basin.

The complete measured pyramid volume, all authored columns and original trees
outside the reservoir are retained. The distant natural lake is a separate
component, not an overlapping second mask.
"""
import argparse,json,msvcrt
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from extend_world_depth_r52 import acquire_world_lock
from query_blocks import iter_block_entities


def smooth(v):
    q=np.clip(v,0,1);return q*q*(3-2*q)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    world=BASE/'WORLD_R52';source=np.load(BASE/'lake_survey/west_reservoir.npz')
    before=source['states'];lo=tuple(map(int,source['origin']));names=list(map(str,source['palette']))
    hi=(lo[0]+before.shape[2]-1,lo[1]+before.shape[0]-1,lo[2]+before.shape[1]-1)
    for state in ('minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]','minecraft:water[level=0]',
                  'minecraft:air','minecraft:black_concrete','projectseele:nerv_structural_panel','projectseele:nerv_floor_panel'):
        if state not in names:names.append(state)
    ids={s:i for i,s in enumerate(names)}
    yy,zz,xx=np.ogrid[:before.shape[0],:before.shape[1],:before.shape[2]]
    x,y,z=xx+lo[0],yy+lo[1],zz+lo[2]
    pyramid=np.broadcast_to(np.maximum(abs(x-30),abs(z-327))<=np.minimum(120,np.ceil((-384-y)*120/174))+1,before.shape)
    natural={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone','minecraft:dirt','minecraft:grass_block',
        'minecraft:water','minecraft:gravel','minecraft:sand','minecraft:clay','minecraft:coarse_dirt','minecraft:tuff',
        'minecraft:podzol','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:azure_bluet','minecraft:poppy','minecraft:dandelion',
        'minecraft:oak_log','minecraft:oak_leaves','minecraft:birch_log','minecraft:birch_leaves'}
    natural_cells=np.isin(before,[i for i,s in enumerate(names) if s.split('[')[0] in natural])
    foreign_columns=np.any(~natural_cells&~pyramid,axis=0)
    tree_cells=np.isin(before,[i for i,s in enumerate(names) if s.split('[')[0].endswith(('_log','_leaves'))])
    tree_columns=np.any(tree_cells,axis=0)
    lake=((x+310)/310.)**2+((z-340)/200.)**2+.075*np.sin((x+z)/47.)+.045*np.cos(z/37.)
    ground=-478+3.5*np.sin(x/137.)*np.cos(z/193.)+2.4*np.sin((x+z)/67.)
    for gx,gz,h,r in ((420,830,29,310),(-230,1030,17,390),(720,330,11,290)):
        ground+=h*np.exp(-((x-gx)**2+(z-gz)**2)/(r*r))
    distance=np.hypot(np.maximum(np.maximum(-90-x,x-160),0),np.maximum(np.maximum(96-z,z-447),0))
    campus=1-smooth(distance/64);ground=np.floor(ground*(1-campus)-467*campus+.5).astype(int)
    water_area=(x>=-300)&(x<=-31)&(z>=246)&(z<=408)
    dry_area=(lake<1.3)&~water_area&~foreign_columns[None,:,:]&~tree_columns[None,:,:]
    after=before.copy()
    for iy,world_y in enumerate(range(lo[1],hi[1]+1)):
        mask=np.broadcast_to(dry_area[0],before.shape[1:])&~pyramid[iy]&natural_cells[iy]
        desired=np.where(world_y>ground[0],ids['minecraft:air'],np.where(world_y==ground[0],ids['minecraft:grass_block[snowy=false]'],
                 np.where(world_y>=ground[0]-3,ids['minecraft:dirt'],ids['minecraft:stone'])))
        after[iy][mask]=np.broadcast_to(desired,before.shape[1:])[mask]
        # Leaves over the former bank may protect their whole column from
        # grading. Still retire the old water itself; otherwise a handful of
        # preserved source blocks would flood the newly dry former basin.
        old_water=np.isin(before[iy],[i for i,s in enumerate(names) if s.split('[')[0]=='minecraft:water'])
        drain=old_water&np.broadcast_to(((lake<1.3)&~water_area)[0],before.shape[1:])&~pyramid[iy]
        after[iy][drain]=np.broadcast_to(desired,before.shape[1:])[drain]
    # A finite engineered basin, with an earthen embankment outside its three
    # exposed sides. The east side terminates against the original west shell.
    outside_distance=np.hypot(np.maximum(np.maximum(-302-x,x+30),0),np.maximum(np.maximum(244-z,z-410),0))
    embankment=(outside_distance<24)&~water_area&~foreign_columns[None,:,:]&~tree_columns[None,:,:]
    bank_height=np.floor(ground*(smooth(outside_distance/24)) + (-468)*(1-smooth(outside_distance/24))).astype(int)
    assert not np.any(tree_columns & np.broadcast_to(water_area[0],before.shape[1:])), 'Reservoir intersects a tree; whole tree handling required'
    basin=np.broadcast_to(water_area,before.shape)&~pyramid&(y>=-510)&(y<=-467)
    assert np.all(natural_cells[basin]),'Another authored structure occupies the west-face basin'
    for iy,world_y in enumerate(range(lo[1],hi[1]+1)):
        bank=np.broadcast_to(embankment[0],before.shape[1:])&~pyramid[iy]&natural_cells[iy]
        values=np.where(world_y>bank_height[0],ids['minecraft:air'],np.where(world_y==bank_height[0],ids['minecraft:grass_block[snowy=false]'],
            np.where(world_y>=bank_height[0]-3,ids['minecraft:dirt'],ids['minecraft:stone'])))
        after[iy][bank]=np.broadcast_to(values,before.shape[1:])[bank]
        area=basin[iy]
        state='minecraft:air' if world_y>-473 else 'minecraft:water[level=0]' if world_y>-509 else 'minecraft:black_concrete'
        after[iy][area]=ids[state]
        retaining=np.broadcast_to(((x==-300)|(z==246)|(z==408))&water_area,before.shape)[iy]&~pyramid[iy]
        if -510<=world_y<=-468:
            after[iy][retaining]=ids['projectseele:nerv_floor_panel' if world_y==-468 else 'minecraft:black_concrete']
    assert np.array_equal(before[pyramid],after[pyramid]),'Original whole pyramid volume changed'
    water_ids=[i for i,s in enumerate(names) if s.split('[')[0]=='minecraft:water']
    assert not np.any(np.isin(after,water_ids)&np.broadcast_to((lake<1.3)&~water_area,before.shape)&~pyramid),'Old basin source water remains outside the reservoir'
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi))
    for q,t in tags.items():
        px,py,pz=q;assert before[py-lo[1],pz-lo[2],px-lo[0]]==after[py-lo[1],pz-lo[2],px-lo[0]],('Authored device changed',q)
    current,cp=measure(lo,hi)
    assert np.array_equal(np.asarray(names)[before],np.asarray(cp)[current]),'Lake survey changed before application'
    vox.WORLD=world;vox.OUT=BASE/'west_reservoir';vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-960,320))
    count=runs(painter,lo,before,after,names,'R52_west_face_reservoir_and_separate_old_basin_restoration')
    painter.meta.update(root_author=True,artificial_water_bounds=[[-300,-508,246],[-31,-473,408]],pyramid_volume_preserved=True,
        water_only_west_side=True,old_natural_lake_not_overlaid=True,new_distant_natural_lake_pending=True)
    folder=painter.save_plan('west_face_only_reservoir')
    report=dict(world_written=False,changed_cells=count,water_level=-473,basin_bottom=-509,
        west_face_only=True,original_devices_preserved=len(tags),pyramid_mask_cells=int(pyramid.sum()),
        separate_new_natural_lake_pending=True,native_water_containment_and_visual_pending=True)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if not args.apply:return
    assert not list(folder.glob('applied_*'));lock=acquire_world_lock()
    try:report.update(world_written=True,receipt=painter.apply('west_face_only_reservoir',session_lock=lock))
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')


if __name__=='__main__':main()
