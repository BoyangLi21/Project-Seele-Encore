"""Rebind actual room metadata/light points to the Root translated room."""
import argparse,json,copy,hashlib,msvcrt
from pathlib import Path
from r52_spatial_plan import BASE,PYRAMID
from query_blocks import iter_block_entities,read_box
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace

parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,required=True);args=parser.parse_args()
BASE=args.base.resolve();world=BASE/'WORLD'
assert (BASE/'pyramid_move/complete_pyramid_translation/PLAN.json').is_file()
import extend_world_depth_r52 as depth
depth.WORLD=world
out=BASE/'seele_room_binding';out.mkdir(exist_ok=True);assert not(out/'APPLIED.json').exists()
files=('r47_seele_conference.json','r48_seele_lighting.json');raw={name:(world/name).read_bytes()for name in files};docs={n:json.loads(b)for n,b in raw.items()}
room=docs[files[0]]['room'];assert room['feet_y']==-364
for key in('bounds','interior_bounds'):room[key]=[list(PYRAMID.point(p))for p in room[key]]
for key in('floor_y','feet_y','roof_y','foundation_y'):room[key]-=93
for key in('table_and_chair_light_centre','table_centre_r48'):room[key]=list(PYRAMID.point(room[key]))
for m in room['monoliths']:m['centre']=list(PYRAMID.point(m['centre']))
room['route_outside_ring']=[list(PYRAMID.point(p))for p in room['route_outside_ring']]
landing=docs[files[0]]['landing']
for key in('cabin_centre','controller','handoff','reader','reader_standing'):landing[key]=list(PYRAMID.point(landing[key]))
for key in('walk_y','floor_y'):landing[key]-=93
for key in('native_door_plane','shaft_aperture','room_entrance'):landing[key]['y']=[y-93 for y in landing[key]['y']]
tags=dict(iter_block_entities(world,'projectseele:geofront',(14,-483,295),(53,-431,325)))
for endpoint in landing['original_endpoints']:
    endpoint['pos']=list(PYRAMID.point(endpoint['pos']));endpoint['walk_y']-=93;endpoint['physical_cabin_floor_y']-=93
    endpoint['full_nbt']=tags[tuple(endpoint['pos'])].snbt()
for reader in docs[files[0]]['readers']:
    for key in('position','standing','normal_call_button_preserved'):
        if key in reader:reader[key]=list(PYRAMID.point(reader[key]))
    if 'retained_main_component_full_after_NBT'in reader:reader['retained_main_component_full_after_NBT']=tags[tuple(reader['position'])].snbt()
for key in('room_gate_r49','room_readers_r49'):
    docs[files[0]]['access_policy'][key]=[list(PYRAMID.point(p))for p in docs[files[0]]['access_policy'][key]]
lighting=docs[files[1]]
for key in('button','spotlight_anchor_r49','spotlight_target_r49'):lighting[key]=list(PYRAMID.point(lighting[key]))
for key in('ambient','table'):lighting[key]=[list(PYRAMID.point(p))for p in lighting[key]]
for name in files:
    docs[name]['r52_root_translation']=[0,-93,0];docs[name]['r52_original_metadata_sha256']=hashlib.sha256(raw[name]).hexdigest()
for point in [lighting['button']]+lighting['ambient']+lighting['table']:
    point=tuple(map(int,point));states=read_box(world,'projectseele:geofront',point,point);state=states[point]
    assert state.startswith('minecraft:polished_blackstone_button['if list(point)==lighting['button']else'minecraft:light['),(point,state)
outputs={name:(json.dumps(docs[name],ensure_ascii=False,indent=2)+'\n').encode('utf8')for name in files};lock=acquire_world_lock();written=[]
try:
    for name in files:
        assert(world/name).read_bytes()==raw[name];(out/('before_'+name)).write_bytes(raw[name]);atomic_replace(world/name,outputs[name]);written.append(name)
    for name in files:assert(world/name).read_bytes()==outputs[name]
except BaseException:
    for name in reversed(written):atomic_replace(world/name,raw[name])
    raise
finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
report=dict(world_written=True,metadata_files={n:hashlib.sha256(v).hexdigest()for n,v in outputs.items()},all_23_actual_light_points_and_button_match=True,
            actual_mid_floor=-457,actual_light_button=lighting['button'],room_gate_and_highest_permission_policy_retained=True,
            entities_not_written=True,native_light_button_and_room_access_pending=True)
(out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
