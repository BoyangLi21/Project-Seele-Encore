"""Read only a frozen composed source; author native actions, never write a world."""
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
from collections import Counter
sys.dont_write_bytecode = True
import nbtlib
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import iter_block_entities
from prepare_school_hakone_native_r45 import ActualGeometry

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / 'artifacts/rebuild_r45/candidate_transport_acceptance_sol_v1/nerv_security_full_interface_queue.json'
NORMAL = {'north': (0,-1), 'south': (0,1), 'west': (-1,0), 'east': (1,0)}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text('utf8'))
def write(path, value): Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n','utf8')
def unpack(value):
    value = int(value)
    x, y, z = value >> 38, value & 4095, (value >> 12) & 0x3ffffff
    return (x, y-4096 if y>=2048 else y, z-0x4000000 if z>=0x2000000 else z)

def main(args):
    world, out = args.world.resolve(), args.out.resolve()
    assert world.name == 'world' and world.parent.parent.name == 'composition_candidates', 'Only a named frozen composed source is supported'
    assert not out.exists() and not out.is_relative_to(world), 'Use a fresh artifact destination'
    queue = read(QUEUE)
    readers = [row for row in queue['objects'] if row['kind']=='FULL_NBT_CARD_CONTROLLED_FIXED_READER']
    assert len(readers)==5 and len(queue['objects'])==684
    measured = MeasuredWorld(world)
    for row in readers:
        tag=nbtlib.parse_nbt(row['actual']['full_nbt']);q=row['actual']['pos'];gate=unpack(tag['Gate'])
        measured.box((min(q[0],gate[0])-12,gate[1]-2,min(q[2],gate[2])-12),
                     (max(q[0],gate[0])+12,gate[1]+int(tag['Height'])+2,max(q[2],gate[2])+12))
    measured.box((22,-331,333),(38,-314,351));measured.load()
    assert all(s=='full' for s in measured.status.values()), 'Unfinished frozen reader chunks'
    tags=dict(iter_block_entities(world,'projectseele:geofront',(-400,-600,-300),(400,120,800),selected_chunks=set(measured.selected)))
    marker_path=world/'dimensions/projectseele/geofront/data/projectseele_dead_sea_chamber_r45.dat'
    marker=nbtlib.load(marker_path)['data']
    chamber_images=[dict(pos=list(unpack(image['Pos'])),state_nbt=image['State'].snbt(),full_nbt=image['NBT'].snbt() if 'NBT' in image else None) for image in marker['Images']]
    assert len(chamber_images)==10 and int(marker['OpenTicks'])==200
    world_id=str(marker['WorldUUID']);seed=int(nbtlib.load(world/'level.dat')['Data']['WorldGenSettings']['seed'])
    cases, scopes, unresolved = [], [], []
    for row in readers:
        q=tuple(row['actual']['pos']);tag=tags.get(q);assert tag is not None
        original=nbtlib.parse_nbt(row['actual']['full_nbt'])
        for field in ('Gate','Exit','Width','Height','Clearance','DoorId','AlongX','Linked','ChamberId','ChamberRole'):
            assert tag.get(field)==original.get(field), ('Frozen reader ownership changed',q,field)
        gate=unpack(tag['Gate']);width=int(tag['Width']);height=int(tag['Height']);along=bool(tag['AlongX']);tier=int(tag['Clearance'])
        high='ChamberId' in tag
        reader_face=properties(measured.block(q))['facing'];normal=NORMAL[reader_face]
        operator=[q[0]+.5+normal[0]*2,gate[1],q[2]+.5+normal[1]*2]
        opened={tuple(gate[k]+((lane if along else 0) if k==0 else y if k==1 else (0 if along else lane)) for k in range(3))
                for lane in range(width) for y in range(height)}
        if high: opened.add((30,-322,339))
        class OpenImage:
            def __init__(self): self.world=world
            def block(self, point): return 'minecraft:air' if tuple(point) in opened else measured.block(point)
            def get(self,x,y,z): return self.block(tuple(map(math.floor,(x,y,z))))
        geometry=ActualGeometry(OpenImage())
        if high:
            staging=[36.5,-329,337.5]
            normal=(0, -1) if str(tag.get('ChamberRole',''))=='outside_left' else (0,1)
        else: staging=operator
        bounds=(min(gate[0],q[0])-10,min(gate[2],q[2])-10,max(gate[0],q[0])+10,max(gate[2],q[2])+10)
        if high: bounds=(25,333,37,347)
        def path(a,b):
            assert geometry.standing(a)=='STATIC_STANDING' and geometry.standing(b)=='STATIC_STANDING', ('Unmeasured full-foot staging',q,a,b)
            route=geometry.path((math.floor(a[0]),math.floor(a[2])),(math.floor(b[0]),math.floor(b[2])),bounds,gate[1])
            assert route, ('No complete actual open-image body path',q,a,b,geometry.unknown)
            return [dict(kind='walk',target=point) for point in route[1:]]
        def equip(value, hand='main'): return dict(kind='equip',tier=value,hand=hand)
        def use(block,value,hand='main',**extra): return dict(kind='use',block=list(block),presented_tier=value,hand=hand,settle_ticks=25,**extra)
        def state(opened_value,status):
            action=dict(kind='assert_reader',block=list(q),expect_open=opened_value,status=status)
            if opened_value: action['expected_open_ticks']=200 if high else 120
            return action
        def aperture(clear): return dict(kind='assert_aperture',expect_clear=clear)
        def images(opened_value): return dict(kind='assert_chamber_images',opened=opened_value)
        scope=dict(reader=list(q),reader_full_nbt=tag.snbt(),gate=list(gate),width=width,height=height,along_x=along,door_id=int(tag['DoorId']))
        lanes=[]
        for lane in range(width):
            centre=[gate[0]+(lane+.5 if along else .5),gate[1],gate[2]+(.5 if along else lane+.5)]
            front=[centre[0]+normal[0],gate[1],centre[2]+normal[1]]
            back=[centre[0]-normal[0],gate[1],centre[2]-normal[1]]
            assert geometry.standing(front)==geometry.standing(back)=='STATIC_STANDING'
            assert geometry.clear(front,target=back)=='CLEAR', ('Actual open full-width lane fails',q,lane)
            lanes.append(dict(front=front,centre=centre,back=back))
        scopes.append(dict(id=row['id'],kind=row['kind'],scope=scope,staging=staging,operator=operator,
                           lanes=lanes,static_shape_unknown=sorted(geometry.unknown),native_passed=False))
        if high and str(tag['ChamberRole'])=='inside_exit':
            # Begin outside; a real granted entrance is mandatory before any inside-reader test.
            entry_q=(36,-328,339);steps=[equip(3),use(entry_q,3),images(True)]
            first=lanes[1]
            steps+=path(staging,first['back'])+path(first['back'],first['front'])+path(first['front'],operator)
            steps+=[dict(kind='hold',ticks=220),images(False),aperture(False)]
        else: steps=[dict(kind='hold',ticks=40),aperture(False)]
        for denied in ([0,1] if high else [0]):
            steps += [equip(denied),use(q,denied),state(False,3),aperture(False)]
        steps += [equip(tier),use(q,tier,swap_after_ticks=1),state(False,3),aperture(False)]
        for hand in ('main','off'):
            steps += [equip(tier,hand),use(q,tier,hand),state(True,2),aperture(True)]
            if high: steps += [images(True)]
            for lane in lanes:
                # A sweep of seven lanes can exceed the real six-second lease.
                # Re-present the actual fixed reader for each independent lane;
                # never lengthen the production authorization window for QA.
                steps += [equip(tier,hand),use(q,tier,hand),state(True,2),aperture(True)]
                steps += path(operator,lane['front'])+path(lane['front'],lane['back'])+path(lane['back'],lane['front'])+path(lane['front'],operator)
            hold_lane=lanes[len(lanes)//2]
            steps += [equip(tier,hand),use(q,tier,hand),state(True,2),aperture(True)]
            steps += path(operator,hold_lane['centre'])+[dict(kind='hold',ticks=220 if high else 145,expect_clear=True),aperture(True)]
            if high: steps += [state(False,0),images(True)]
            steps += path(hold_lane['centre'],operator)+[dict(kind='hold',ticks=35),aperture(False)]
            if high: steps += [images(False)]
        if not high:
            exit_q=unpack(tag['Exit']);assert exit_q!=(0,0,0)
            exit_face=properties(measured.block(exit_q)).get('facing');assert exit_face in NORMAL, ('Missing fixed release input',q,exit_q)
            dx,dz=NORMAL[exit_face];exit_operator=[exit_q[0]+.5+dx*2,gate[1],exit_q[2]+.5+dz*2]
            # Reach the release from a real granted crossing; do not teleport inside.
            middle=lanes[len(lanes)//2]
            steps += [equip(tier),use(q,tier),aperture(True)]+path(operator,middle['front'])+path(middle['front'],middle['back'])+path(middle['back'],exit_operator)
            steps += [dict(kind='hold',ticks=145),aperture(False),equip(0),use(exit_q,0),aperture(True)]
            steps += path(exit_operator,middle['back'])+path(middle['back'],middle['front'])+path(middle['front'],operator)
            steps += [dict(kind='hold',ticks=145),aperture(False)]
        if high: steps += [dict(kind='assert_archive',block=[30,-329,345])]
        cases.append(dict(scope,id=row['id']+'/full_native_cycle',staging=staging,steps=steps,
                          action_count=len(steps),native_passed=False,no_card_inside_rescue='UNVERIFIED_SECOND_AUTHORIZED_CLIENT_REQUIRED'))
    uncovered=[dict(id=r['id'],kind=r['kind'],required=r['required'],status='UNVERIFIED_OBJECT_REQUIRES_ITS_OWN_PURPOSE_AND_RUNTIME_CONTROL') for r in queue['objects'] if 'READER' not in r['kind']]
    binding=None
    if args.binding:
        binding=read(args.binding)
        assert binding['world_id']==world_id and int(binding['world_seed'])==seed
    job=dict(schema='projectseele.nerv-security-native-cases-r45.v1',bound=bool(binding),
             world=binding['world'] if binding else str(world),world_id=world_id,world_seed=seed,
             candidate_binding=str(args.binding.resolve()) if binding else 'ROOT_MUST_REBIND_NEW_COLD_CHECKPOINT',
             candidate_binding_sha256=sha(args.binding) if binding else 'UNBOUND',cases_required=len(cases),reader_objects_required=5,
             total_security_objects=684,cases=cases,chamber_images=chamber_images,uncovered_objects=uncovered,
             tier2='NOT_INSTALLED_NO_FAKE_CARD_TEST',native_passed=False,full_lifecycle_pass=False,
             frozen_source=str(world),source_queue_sha256=sha(QUEUE),frozen_chamber_marker_sha256=sha(marker_path),
             source_native_shape_sha256=sha(world/'native_collision_shapes.json'),
             archive_native_shape_status='CURRENT_SOURCE_CONSUMER_MUST_CAPTURE_ACTUAL_COLLISION_NOT_INHERIT_OLD_EXPORT',
             pending=['same_JVM_reload','cold_reload','save_interrupt','disconnect_before_grant','two_clients','no_card_inside_expired_rescue'])
    out.mkdir(parents=True)
    write(out/'nerv_security_native_job.json',job);write(out/'all5_reader_open_image_path_evidence.json',scopes)
    write(out/'prepare_receipt.json',dict(world_written=False,java_mc_gradle_launched=False,cases=len(cases),actions=sum(c['action_count'] for c in cases),objects=684,
         untested_other_objects=len(uncovered),reader_native_pass=False,full_lifecycle_pass=False,job_sha256=sha(out/'nerv_security_native_job.json'),static_open_image_only=True))
    print(json.dumps(read(out/'prepare_receipt.json'),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--binding',type=Path)
    main(p.parse_args())
