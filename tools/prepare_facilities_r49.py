"""R49 finite, measured room/door/lighting candidate; never writes a world."""
from pathlib import Path
import argparse, copy, json, uuid
import nbtlib
from prepare_facilities_r48 import Author, DIM
from query_blocks import AIR

ROOT = Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--world', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=ROOT/'artifacts/rebuild_r49/facilities')
    args = ap.parse_args()
    a = Author(args.world.resolve(), args.out.resolve())
    a.out.mkdir(parents=True, exist_ok=True)
    metadata = []
    def file_patch(name, after):
        p = a.world/name
        before = json.loads(p.read_text('utf8')) if p.is_file() else None
        target = a.out/name
        target.write_text(json.dumps(after, ensure_ascii=False, indent=2), 'utf8')
        metadata.append(dict(relative_target=name, before=before, after=after))

    d = {}; doors = []
    for v in range(3):
        x = 7+42*v
        a.read((x-4,-395,-228),(x+2,-390,-216))
        for y, half in ((-394,'lower'),(-393,'upper')):
            q = x,y,-223
            assert a.s[q] == 'projectseele:nerv_room_partition[east=true,north=true,south=false,west=false]' and q not in a.t
            d[q] = (f'projectseele:city_personnel_door[facing=south,half={half},hinge=right,open=false,powered=false]', 'User-authorized guard-facing north room door; original phone, seat and bridge door retained', None)
        route = [[x-1+.5,-394,-219.5],[x-1+.5,-394,-220.5],[x+.5,-394,-220.5],
                 [x+.5,-394,-221.5],[x+.5,-394,-222.5],[x+.5,-394,-223.5],[x+.5,-394,-224.5],[x+.5,-394,-225.5]]
        for z in range(-225,-219):
            assert a.s[x,-395,z] not in AIR
            assert a.s[x+1,-394,z] not in AIR, ('East boundary lacks actual backing',v,z)
        doors.append(dict(variant=v,lower=[x,-394,-223],facing='south',hinge='right',inside=[x+.5,-394,-221.5],outside=[x+.5,-394,-223.5],route=route))
    a.emit('F01_guard_facing_pilot_doors', d, dict(first_error=[7,-394,-223], affected=[[7,-394,-223],[49,-394,-223],[91,-394,-223]], north_wall_closed=True, central_phone_not_a_corridor=True, original_phone_seat_west_door_UUID_unchanged=True, doors=doors))
    marker = dict(schema=49, dimension=DIM, installed=True, pilot_guard_doors=doors,
                  gate_lower=[[28,-364,315],[29,-364,315]],
                  gate_readers=[[27,-363,314],[27,-363,316]], gate_clearance=3,
                  meeting_block_light=0, spotlight_anchor=[34.5,-356.85,308.3],
                  spotlight_target=[34.5,-362.96,308.3])
    file_patch('r49_facility_controls.json', marker)
    rooms = json.loads((a.world/'r47_pilot_restrooms.json').read_text('utf8'))
    for slot, door in zip(rooms['slots'], doors): slot['guard_door_r49'] = door
    file_patch('r47_pilot_restrooms.json', rooms)

    a.read((12,-370,298),(55,-354,330))
    d = {}
    # Finite vestibule between the original room wall at315 and lift door317.
    # The original reader at31/316 keeps its entire NBT and its backing at317.
    for x in (25,32):
        for y in range(-365,-355):
            q = x,y,316
            assert q not in a.t and a.s[q] in AIR|{'projectseele:nerv_floor_panel'}
            d[q] = ('minecraft:black_concrete','Close full side return of actual SEELE lift vestibule without entering the cabin/landing-door sweep',None)
    for x in range(26,32):
        q = x,-356,316
        assert a.s[q] in AIR and q not in a.t
        d[q] = ('minecraft:black_concrete','Continuous vestibule roof joins existing room roof and lift header',None)
    for x in range(26,31):
        for y in range(-364,-361):
            q = x,y,315
            assert a.s[q] in AIR and q not in a.t
            if x in (28,29) and y<=-363:
                half = 'lower' if y==-364 else 'upper'
                hinge = 'right' if x==28 else 'left'
                state = f'projectseele:city_personnel_door[facing=south,half={half},hinge={hinge},open=false,powered=false]'
            else: state = 'minecraft:black_concrete'
            d[q] = (state,'Complete fixed highest-card door and frame at original room entry plane',None)
    sample = copy.deepcopy(a.t[31,-363,316])
    for z, facing, label in ((314,'north','SEELE · 最高卡出门'),(316,'south','SEELE · 最高卡进门')):
        q = 27,-363,z
        assert a.s[q] in AIR and q not in a.t
        tag = copy.deepcopy(sample)
        tag['x'],tag['y'],tag['z'] = (nbtlib.Int(n) for n in q)
        tag['Linked']=nbtlib.Byte(0);tag['Label']=nbtlib.String(label)
        tag['Width']=nbtlib.Int(2);tag['Height']=nbtlib.Int(2);tag['Clearance']=nbtlib.Int(3)
        tag['Gate']=nbtlib.Long((28<<38)|(315<<12)|(-364&4095))
        for k in ('OpenUntil','IndicateUntil'): tag[k]=nbtlib.Long(0)
        tag['SwipeAt']=nbtlib.Long(-1)
        for k in ('Presented','Status'): tag[k]=nbtlib.Int(0)
        if 'User' in tag: del tag['User']
        d[q]=(f'projectseele:nerv_access_reader[facing={facing}]','Separate actual reader on each side; finite service owns card-only door, complete native reader factory NBT retained',tag)
    stairs=[dict(pos=list(q),state=s) for q,s in a.s.items() if 'stairs[' in s or 'escalator_step[' in s]
    a.emit('F02_closed_seele_vestibule_gate',d,dict(first_error=[25,-364,316],air_gap_between_room315_and_lift317=True,gate_readers=marker['gate_readers'],gate_lower=marker['gate_lower'],original_lift_reader_NBT_and_317_door_and_318_324_cabin_sweep_retained=True,adjacent_stairs_measured=stairs,highest_card_both_directions=True,unconditional_meeting_egress_retired=True))
    conference=json.loads((a.world/'r47_seele_conference.json').read_text('utf8'))
    conference['access_policy']['middle_egress_without_card']=False
    conference['access_policy']['room_gate_r49']=marker['gate_lower']
    conference['access_policy']['room_readers_r49']=marker['gate_readers']
    conference['access_policy']['native_function_passed']=False
    for r in conference['readers']:
        if r['position']==[31,-363,316]:r['role']='admission_and_highest_card_egress'
    file_patch('r47_seele_conference.json',conference)

    lighting=json.loads((a.world/'r48_seele_lighting.json').read_text('utf8'))
    # A Minecraft light emits in all directions. Meeting removes ALL these
    # sources; the finite desk renderer receives only the overhead soft focus.
    lighting['meeting_all_block_lights_zero_r49']=True
    lighting['spotlight_anchor_r49']=marker['spotlight_anchor']
    lighting['spotlight_target_r49']=marker['spotlight_target']
    file_patch('r48_seele_lighting.json',lighting)
    d={}
    for q in lighting['ambient']+lighting['table']:
        p=tuple(q);assert a.s[p].startswith('minecraft:light[') and p not in a.t
        # Construction keeps daily mode; runtime commits the persistent meeting
        # value. Recording the full list proves the complete old source set.
    a.emit('F03_seele_lighting_contract',d,dict(first_error=[32,-364,307],old_meeting_table_block_light=[12,14],new_meeting_all_23_block_lights=0,daily_block_light=14,old_lower_omnidirectional_table_glow_retired=True,overhead_anchor=marker['spotlight_anchor'],native_and_visual_verified=False))
    a.recipe()
    (a.out/'metadata_patch.json').write_text(json.dumps(dict(schema=49,operations=metadata,world_written=False),ensure_ascii=False,indent=2),'utf8')
    for component in a.components:
        component['schema']='projectseele.r49.facility-candidate.v1'
        component['authorization']='User R49 guard-facing doors, sealed SEELE lift sides, highest-card ingress/egress and overhead-only meeting light'
    for folder in a.out.glob('F*/contract.json'):
        data=json.loads(folder.read_text('utf8'));data.update(schema='projectseele.r49.facility-candidate.v1',authorization=a.components[0]['authorization']);folder.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    identities=nbtlib.load(a.world/'dimensions/projectseele/geofront/data/projectseele_seele_conference_r47.dat')['data']['Monoliths']
    ids={k:str(uuid.UUID(bytes=b''.join((int(n)&0xffffffff).to_bytes(4,'big') for n in value))) for k,value in identities.items()}
    (a.out/'manifest.json').write_text(json.dumps(dict(schema=49,components=a.components,total_cells=len(a.all),world_written=False,original_conference_UUIDs=ids,native_verified=False,visual_verified=False,reference='User R49 dark room overhead light direction; official web_screen browsing does not authorize importing official pixels'),ensure_ascii=False,indent=2),'utf8')
    print('R49 candidate',len(a.all),'cells; complete old/new NBT, inverse, metadata and static generation recipe; no world writes')

if __name__=='__main__': main()
