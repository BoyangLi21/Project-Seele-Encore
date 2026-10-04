"""Whole authorized room/port and permission/lease reference checks, no JVM/world writes."""
import sys,json,gzip,copy,ast,re,hashlib
from pathlib import Path
from collections import Counter,deque
sys.dont_write_bytecode=True
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR
from prepare_school_hakone_native_r45 import ActualGeometry
from install_city_rigid_metadata_r45 import same_tag
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r45/dead_sea_chamber_sol_followup';PLAN=OUT/'component_v2';WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    rows=[json.loads(x) for x in gzip.open(PLAN/'forward.jsonl.gz','rt',encoding='utf8')];inverse=[json.loads(x) for x in gzip.open(PLAN/'inverse.jsonl.gz','rt',encoding='utf8')]
    assert len(rows)==len(inverse)==len({tuple(r['pos']) for r in rows})
    w=MeasuredWorld(WORLD);w.box((22,-331,333),(38,-314,351));w.load();tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(22,-331,333),(38,-314,351)))
    before_errors=[]
    for r,b in zip(rows,inverse):
        assert r['pos']==b['pos'] and (r['before'],r['after'],r['before_nbt'],r['after_nbt'])==(b['after'],b['before'],b['after_nbt'],b['before_nbt'])
        q=tuple(r['pos']);actual=tags[q].snbt() if q in tags else None
        if w.block(q)!=r['before'] or actual!=r['before_nbt']:before_errors.append(q)
    assert not before_errors
    target={tuple(r['pos']):r['after'] for r in rows};portal={(x,y,340) for x in range(32,35) for y in range(-329,-326)}
    class Ghost:
        world=w.world
        def __init__(self,opened):self.opened=opened
        def block(self,q):
            q=tuple(q)
            if self.opened and (q in portal or q==(30,-322,339)):return 'minecraft:air'
            return target.get(q,w.block(q))
        def get(self,x,y,z):
            import math
            return self.block((math.floor(x),math.floor(y),math.floor(z)))
    geometry=ActualGeometry(Ghost(True));feet=-329;legal=[];census=Counter()
    for x in range(25,36):
        for z in range(341,348):
            status=geometry.standing([x+.5,feet,z+.5]);census[status]+=1
            if status=='STATIC_STANDING':legal.append((x,z))
    start=(33,341);seen={start};todo=deque([start])
    while todo:
        x,z=todo.popleft()
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            q=x+dx,z+dz
            if q in legal and q not in seen and geometry.clear([x+.5,feet,z+.5],target=[q[0]+.5,feet,q[1]+.5])=='CLEAR':seen.add(q);todo.append(q)
    assert set(legal)==seen,'All user-authorized room footprints must connect to the actual portal'
    closed=ActualGeometry(Ghost(False));port_evidence=[]
    for x in (32,33,34):
        a=[x+.5,-329,339.5];b=[x+.5,-329,341.5]
        assert geometry.standing(a)==geometry.standing(b)=='STATIC_STANDING' and geometry.clear(a,target=b)=='CLEAR'
        assert closed.clear(a,target=b)=='ACTUAL_BODY_OBSTRUCTION'
        port_evidence.append(dict(front=a,rear=b,open_complete_body_sweep='CLEAR',closed_complete_body_sweep='BLOCKED'))
    points=dict(outside_reader=[36.5,-329,337.5],inside_reader=[35.5,-329,343.5],book_front=[30.5,-329,343.5])
    assert all(geometry.standing(point)=='STATIC_STANDING' for point in points.values())
    preserved=json.loads((PLAN/'preserved_full_BE.json').read_text('utf8'))
    assert all(w.block(tuple(r['pos']))==r['state'] and tags[tuple(r['pos'])].snbt()==r['full_snbt'] for r in preserved)
    book_move=next(r for r in rows if r['pos']==[30,-329,345]);original=tags[(30,-329,340)];moved=nbtlib.parse_nbt(book_move['after_nbt']);expected=copy.deepcopy(original)
    for k,v in zip(('x','y','z'),(30,-329,345)):expected[k]=nbtlib.Int(v)
    assert same_tag(moved,expected)
    marker=nbtlib.load(PLAN/'projectseele_dead_sea_chamber_r45.dat')['data'];assert int(marker['OpenTicks'])==200 and len(marker['Images'])==10
    # Permission window model: same hand, highest at presentation and grant,
    # in range, live original actor. Never a cardless Exit-button lease.
    cases=[]
    for presented in (0,1,2,3):
        for held in (0,1,2,3):
            grant=presented>=3 and held>=3;cases.append(dict(presented=presented,held_at_decision=held,granted=grant))
    assert sum(c['granted'] for c in cases)==1
    now=500;deadline=now+200
    assert 699<deadline and not 700<deadline
    expired_occupied=dict(authority_until=deadline,tick=700,physical_safety_hold=True,new_permission_granted=False)
    assert expired_occupied['authority_until']==700
    source=ROOT/'src/main/java/com/projectseele/world/NervAccessReaderEntityR44.java';text=source.read_text('utf8')
    assert 'openUntil=now+120' in text and 'openUntil=level.getGameTime()+120' in text
    assert 'reader.tickChamber(level);return' in text and 'DeadSeaChamberR45.handles(this))return' in text
    title=ROOT/'src/main/java/com/projectseele/client/DeadSeaArchiveScreenR45.java';prior=(OUT/'source_before'/title.name).read_text('utf8');current=title.read_text('utf8')
    assert current==prior.replace('Component.literal("秘密死海文书 · 译注档案")','Component.literal("死海文书")',1)
    files=[ROOT/'src/main/java/com/projectseele/world/DeadSeaChamberSavedDataR45.java',ROOT/'src/main/java/com/projectseele/world/DeadSeaChamberR45.java',source,title];epochs=[]
    for file in files:
        value=file.read_text('utf8');plain=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*[\s\S]*?\*/|//[^\n]*','',value);stack=[];pair={'}':'{',')':'(',']':'['}
        for ch in plain:
            if ch in '({[':stack.append(ch)
            elif ch in ')}]':assert stack and stack.pop()==pair[ch],file
        assert not stack,file
        epochs.append(dict(source=str(file),sha256=sha(file),Java_compiled_by_agent=False))
    for p in [Path(__file__),ROOT/'tools/prepare_dead_sea_chamber_r45.py',ROOT/'tools/install_dead_sea_archive_r45.py',ROOT/'tools/mount_wall_art_r42.py']:ast.parse(p.read_text('utf8'))
    report=dict(exact_mask_cells=len(rows),full_before_NBT_preconditions_errors=before_errors,inverse_complete=True,
        original_full_BE_preserved=len(preserved),book_only_xyz_changed=True,room_declared_columns=77,whole_room_classes=dict(census),all_connected_room_columns=len(legal),
        full_three_width_portal_both_sides=port_evidence,native_operator_points=points,unknown_native_shape_states=sorted(geometry.unknown),
        clearance_reference_cases=cases,expired_occupied_reference=expired_occupied,ordinary_other_readers_120tick_lease_preserved=True,
        title_only_one_string_changed=True,source_epoch=epochs,world_written=False,native_pass=False,art_pass=False,
        runtime_requirements=['Root compiles the exact current epoch','Root applies static component+dedicated marker, original actors/progress never copied','Real tier0/1/2 denial and tier3 main/offhand swipe','Swap/remove/disconnect before tick6 deny','Exact200 tick window, both sides, all3 width lanes','Occupied expiration safety without new grant','Inside highest-reader exit after expiry','Real readable original book/page0/tree root asset','Mixed OPENING/CLOSING normal restart, foreign fullNBT HOLD','Final native shaders/still photos and full delivered-copy readback'])
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8')
    print('Exact/inverse',len(rows),'room connected',len(legal),'of',len(legal),'full width3 open/closed; permission model16; ordinary leases preserved; no JVM/world write')
if __name__=='__main__':main()
