"""Retire vacated old observation floors while keeping the original metro link.

The unchanged EVA station still uses -442 and the real experimental lab -468.
Move the original empty native car to -442 and retain exactly these two stops.
"""
import argparse,copy,json,msvcrt
import nbtlib
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE,Frame
from facility_frame_nbt_r52 import block_entity_in_frame
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from prepare_pyramid_move_r52 import encoded
from move_component_actors_r52 import prepare_actor_files
from extend_world_depth_r52 import acquire_world_lock
from query_blocks import iter_block_entities
from apply_s20_approved_semantic_repairs import atomic_replace


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    world=BASE/'WORLD_R52';lo=(88,-469,-85);hi=(114,-310,-15)
    before,names=measure(lo,hi);names=list(names)
    for s in ('minecraft:air','projectseele:nerv_structural_panel','minecraft:stone','minecraft:grass_block[snowy=false]'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)};after=before.copy();owned=np.zeros(before.shape,bool)
    def sl(b):
        x,y,z,X,Y,Z=b
        assert lo[0]<=x<=X<=hi[0] and lo[1]<=y<=Y<=hi[1] and lo[2]<=z<=Z<=hi[2]
        return np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]
    def own(b):owned[sl(b)]=True
    own((88,-371,-84,113,-363,-16))
    own((95,-398,-84,114,-388,-42))
    own((89,-436,-56,99,-363,-48))
    for x in (89,112):
        for z in (-82,-18):own((x,-467,z,x,-372,z))
    # The original surface shaft shares this boundary; it is retained whole.
    owned[sl((88,-469,-54,89,-310,-18))]=False
    ys=np.arange(before.shape[0])[:,None,None]+lo[1]
    fill=np.broadcast_to(np.where(ys>-467,ids['minecraft:air'],np.where(ys==-467,ids['minecraft:grass_block[snowy=false]'],ids['minecraft:stone'])),before.shape)
    after[owned]=fill[owned]
    # Source car is frozen exactly before removing the upper storeys.
    car=before[sl((91,-395,-54,95,-389,-50))].copy()
    frozen=np.load(BASE/'survey/original_hangar_transfer_launch.npz');origin=frozen['origin']
    original=frozen['states'][-395-origin[1]:-389-origin[1]+1,-54-origin[2]:-50-origin[2]+1,91-origin[0]:95-origin[0]+1]
    assert np.array_equal(np.asarray(names)[car],frozen['palette'][original]),'Original compact car differs from frozen source'
    assert all(names[int(v)]=='minecraft:polished_deepslate' for v in car[0].flat)
    after[sl((91,-443,-54,95,-437,-50))]=car
    after[sl((89,-436,-56,99,-436,-48))]=ids['projectseele:nerv_structural_panel']
    current=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));additions={}
    refs={(96,y,-52):(96,y,-52) for y in (-468,-442)}
    for q,t in current.items():
        if 91<=q[0]<=95 and -395<=q[1]<=-389 and -54<=q[2]<=-50:
            n=block_entity_in_frame(t,Frame(0,0,-48,0),reference_positions=refs)
            p=tuple(int(n[k]) for k in ('x','y','z'));additions[p]=n
    assert len(additions)==2,'Original in-car panel/display expected'
    for q,t in current.items():
        x,y,z=q
        if before[y-lo[1],z-lo[2],x-lo[0]]!=after[y-lo[1],z-lo[2],x-lo[0]]:
            assert str(t['id']).startswith('movingelevators:') and y>=-394,('Unrelated device',q,str(t['id']))
    from verify_main_r20 import entities
    for t in entities(world).values():
        x,y,z=map(float,t['Pos'])
        assert not (89<=x<100 and -443<=y<=-388 and -56<=z<-47),'Actual actor in native car/shaft'
    vox.WORLD=world;vox.OUT=BASE/'old_observation_retirement';vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-960,320))
    count=runs(painter,lo,before,after,names,'R52_retire_vacated_old_observation_components')
    for q,t in additions.items():
        x,y,z=q;state=names[int(after[y-lo[1],z-lo[2],x-lo[0]])]
        painter.block_entities[q]=t
        if before[y-lo[1],z-lo[2],x-lo[0]]==after[y-lo[1],z-lo[2],x-lo[0]]:painter.update_block_entity(q,state,current.get(q),t,'R52_original_native_cabin_panel_descends_48m')
    # Retained controller name describes its unchanged physical station role.
    q=(96,-442,-52);t=copy.deepcopy(current[q]);t['data']['name']=nbtlib.String('原机库站接驳层')
    painter.update_block_entity(q,names[int(before[q[1]-lo[1],q[2]-lo[2],q[0]-lo[0]])],current[q],t,'R52_original_station_floor_label')
    painter.meta.update(root_author=True,original_station_and_tracks_unchanged=True,old_lift_retained_floors=[-468,-442],
        original_car_translation_y=-48,original_car_geometry=True,vacated_upper_stop_retirement=True)
    folder=painter.save_plan('old_observation_retired_station_link_retained')
    report=dict(world_written=False,changed_cells=count,original_cabin_moved_y=-48,retained_floors=[-468,-442],retired_floors=[-394,-370],
        native_station_database_untouched=True,remaining_separate_component='earlier basement deck and old emergency facade',native_review_pending=True)
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if not args.apply:return
    assert not list(folder.glob('applied_*'));lock=acquire_world_lock();path=world/'dimensions/projectseele/geofront/data/capabilities.dat';raw=path.read_bytes();geometry=None
    try:
        caps=nbtlib.load(path);group=caps['data']['movingelevators:elevator_groups']['96;-52']['group']
        assert not bool(group['isMoving']) and list(map(int,group['floors']))==[-468,-442,-394,-370]
        assert [bool(v['isCageAvailable']) for v in group['floorData']]==[False,False,True,False]
        group['floors']=nbtlib.IntArray([-468,-442]);group['floorData']=nbtlib.List[nbtlib.Compound](list(group['floorData'])[:2])
        group['floorData'][1]['isCageAvailable']=nbtlib.Byte(1);group['floorData'][1]['name']=nbtlib.String('原机库站接驳层')
        (folder/'capabilities_before.dat').write_bytes(raw)
        geometry=painter.apply('old_observation_retired_station_link_retained',session_lock=lock)
        assert path.read_bytes()==raw;atomic_replace(path,encoded(caps))
        report.update(world_written=True,receipt=geometry)
        (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    except BaseException:
        atomic_replace(path,raw)
        if geometry is not None:
            app=list(folder.glob('applied_*'));assert len(app)==1
            for f in (app[0]/'before').glob('r.*.mca'):atomic_replace(world/'dimensions/projectseele/geofront/region'/f.name,f.read_bytes())
            (app[0]/'ROLLED_BACK.json').write_text('{"reason":"compact group migration failed"}','utf8')
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
