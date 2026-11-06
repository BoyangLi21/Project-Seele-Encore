"""Move the COMPLETE Terminal layer below the real 64m carrier service pits.

Keep both original actors, all typed lift state, and the same shared elevator.
The existing intermediate floors and the car at the HQ level do not move.
"""
import argparse,copy,json,msvcrt
import numpy as np
import nbtlib
import regional_voxels as vox
from r52_spatial_plan import BASE,Frame
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from prepare_pyramid_move_r52 import encoded
from query_blocks import iter_block_entities,read_box
from facility_frame_nbt_r52 import block_entity_in_frame
from move_component_actors_r52 import prepare_actor_files,identity
from verify_main_r20 import entities
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';out=BASE/'terminal_service_clearance';stage='complete_terminal_extra_80m';folder=out/stage
    assert not list(folder.glob('applied_*')),'Never replay a whole-room translation'
    lo=(-56,-927,225);hi=(116,-716,413);before,names=measure(lo,hi)
    for s in ('minecraft:deepslate[axis=y]','projectseele:nerv_structural_panel','minecraft:air'):
        if s not in names:names.append(s)
    ids={s:i for i,s in enumerate(names)};after=before.copy()
    def sl(b):
        x,y,z,X,Y,Z=b;assert lo[0]<=x<=X<=hi[0]and lo[1]<=y<=Y<=hi[1]and lo[2]<=z<=Z<=hi[2]
        return np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]
    old_box=(-56,-847,225,116,-716,413);new_box=(-56,-927,225,116,-796,413)
    room=before[sl(old_box)].copy()
    # Entire overlap-safe snapshot, including the already authored bottom
    # landing and complete gallery. Deeper untouched destination is geology.
    assert {names[int(v)]for v in np.unique(before[:80])}<={'minecraft:deepslate[axis=y]','minecraft:deepslate'}
    after[sl(old_box)]=ids['minecraft:deepslate[axis=y]']
    after[sl((104,-848,403,112,-716,411))]=ids['projectseele:nerv_structural_panel']
    after[sl((105,-847,404,111,-716,410))]=ids['minecraft:air']
    after[sl(new_box)]=room
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));assert len(tags)==3 and {str(t['id'])for t in tags.values()}=={'movingelevators:elevator_tile','movingelevators:button_tile','movingelevators:display_tile'},[(q,str(t['id']))for q,t in tags.items()]
    frame=Frame(0,0,-80,0);references={(108,-766,410):(108,-846,410)}
    moved_tags={frame.block(q):block_entity_in_frame(t,frame,reference_positions=references)for q,t in tags.items()}
    actors=entities(world);wanted={}
    for tag in actors.values():
        pos=list(map(float,tag.get('Pos',[])))
        if len(pos)==3 and all(old_box[i]<=pos[i]<=old_box[i+3]for i in range(3)):wanted[identity(tag)]=tag
    assert set(wanted)=={'5102dc56-c4e4-4e74-b66b-79f70fde6ced','1768a5fb-4caf-463d-96f8-be1364f5f9ba'},wanted.keys()
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320))
    n=runs(p,lo,before,after,names,'R52_whole_terminal_clear_of_carrier_service_pits');p.block_entities.update(moved_tags)
    # The unchanged car's internal native button points at the lowest
    # controller. Move its reference, never the car or its existing contents.
    shaft_tags=dict(iter_block_entities(world,'projectseele:geofront',(104,-715,403),(112,-548,411)))
    relinked=[]
    for q,t in shaft_tags.items():
        d=t.get('data',{})
        if all(k in d for k in('controllerX','controllerY','controllerZ'))and tuple(int(d[k])for k in('controllerX','controllerY','controllerZ'))==(108,-766,410):
            new=copy.deepcopy(t);new['data']['controllerY']=type(d['controllerY'])(-846);state=read_box(world,'projectseele:geofront',q,q)[q]
            p.update_block_entity(q,state,t,new,'R52_same_shared_car_new_lowest_controller');relinked.append(q)
    assert len(relinked)==1,relinked
    p.meta.update(root_author=True,complete_room=True,source_box=old_box,destination_box=new_box,shared_lift_same_group=True)
    folder=p.save_plan(stage);report=dict(world_written=False,changed_cells=n,old_room_box=old_box,new_room_box=new_box,
                minimum_mechanical_storage_clearance_to_room_roof=53,whole_room_translation=[0,-80,0],original_lilith_uuid='5102dc56-c4e4-4e74-b66b-79f70fde6ced',
                new_lilith=[30.5,-880,348.5],new_shared_bottom_stop=[108,-846,407],moved_native_devices=len(moved_tags),relinked_cabin_buttons=relinked,
                original_other_actors_count=len(actors)-2,intermediate_lift_floors_unchanged=True,
                pending=['updated lift manifest','native deep-lift ride and complete room appearance','mechanical pit and watertight shutter'])
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if not args.apply:return
    lock=acquire_world_lock();backups={};geometry=None
    try:
        pending,actor_receipt=prepare_actor_files(world,{k:frame for k in wanted},{k:t.snbt()for k,t in wanted.items()})
        caps_path=world/'dimensions/projectseele/geofront/data/capabilities.dat';caps=nbtlib.load(caps_path);group=caps['data']['movingelevators:elevator_groups']['108;410']['group']
        assert not bool(group['isMoving']) and list(map(int,group['floors']))==[-766,-704,-630,-603,-554] and not bool(group['floorData'][0]['isCageAvailable'])
        group['floors']=nbtlib.IntArray([-846,-704,-630,-603,-554]);pending[caps_path]=encoded(caps)
        roster_path=world/'nerv_staff_r15.json';roster=json.loads(roster_path.read_text('utf8'));guard=next(r for r in roster['stations']if r['id']=='guard/dogma_checkpoint');assert guard['feet']==[12,-766,278];guard['feet']=[12,-846,278];pending[roster_path]=(json.dumps(roster,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        # Existing saved players are outside this controlled layer.
        for path in(world/'playerdata').glob('*.dat'):
            t=nbtlib.load(path);pos=list(map(float,t.get('Pos',[])))
            assert str(t.get('Dimension',''))!='projectseele:geofront' or len(pos)!=3 or not all(old_box[i]<=pos[i]<=old_box[i+3]for i in range(3)),'Player inside moved room needs explicit same-stage move'
        for path in pending:
            backups[path]=path.read_bytes();dest=folder/'metadata_before'/path.relative_to(world);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(backups[path])
        geometry=p.apply(stage,session_lock=lock)
        for path,raw in pending.items():assert path.read_bytes()==backups[path];atomic_replace(path,raw)
        actual,pal=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pal],np.uint16)[actual],after)
        check=entities(world);assert set(check)==set(actors) and len(check)==680
        for key,t in actors.items():
            if identity(t)not in wanted:assert check[key].snbt()==t.snbt()
        current_tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));assert {q:t.snbt()for q,t in current_tags.items()}=={q:t.snbt()for q,t in moved_tags.items()}
        report.update(world_written=True,receipt=geometry,actor_receipt=actor_receipt,all_680_identities_preserved=True,other_678_full_actor_nbt_unchanged=True,whole_room_exact_readback=True)
        (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    except BaseException:
        for path,raw in backups.items():atomic_replace(path,raw)
        if geometry is not None:
            app=list(folder.glob('applied_*'));assert len(app)==1
            for backup in(app[0]/'before').glob('r.*.mca'):atomic_replace(world/'dimensions/projectseele/geofront/region'/backup.name,backup.read_bytes())
            (app[0]/'ROLLED_BACK.json').write_text('{"reason":"Terminal metadata/readback failed"}','utf8')
        raise
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()
