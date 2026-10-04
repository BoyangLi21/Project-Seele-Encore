"""Read frozen commissioned components, classify all null rows and propose exact repairs."""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,math,sys
from pathlib import Path
from collections import deque
sys.dont_write_bytecode=True
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import AIR,iter_block_entities
from prepare_school_hakone_native_r45 import ActualGeometry
from audit_facility_transit_r44 import Geometry
from plan_hangar_upper_enclosure_r44 import protected_public_columns
from hangar_tv_design_r44 import upper_pressure_members

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'artifacts/rebuild_r45/composition_candidates/R45_source_candidate_20261003_v4_01/world'
NAV=ROOT/'artifacts/rebuild_r45/city_transport_xhigh_r45/navigation_hq_v1'
BASELINE=ROOT/'artifacts/rebuild_r45/city_atomic_integration_r45/qa_copy_revision_v1/copy_plan_v2/copy_plan.json'
OLD=ROOT/'artifacts/rebuild_r44/facility_transit_r44/hangar_upper_enclosure_v2/common_upper_pressure_envelope'
ARCHIVE_NATIVE=ROOT/'artifacts/rebuild_r45/native_shapes/fresh_chamber_book_v4/native_collision_shapes.json'
ARCHIVE_CLASS_SHA='00a66011d954d3f8fc11d4b2987b425a470981815092e1f959bb6c7c77fe11fd'
def read(p):return json.loads(Path(p).read_text('utf8'))
def gzread(p):
    with gzip.open(p,'rt',encoding='utf8')as f:return json.load(f)
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n','utf8')
def jsonl(p,rows):
    with gzip.GzipFile(filename=str(p),mode='wb',mtime=0)as f:
        for row in rows:f.write((json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf8'))

def main(args):
    out=args.out.resolve();assert not out.exists() and not out.is_relative_to(WORLD)
    baseline=read(BASELINE);expected={r['relative']:r['sha256']for r in baseline['files']};assert len(expected)==1736
    def inventory():
        names={p.relative_to(WORLD).as_posix()for p in WORLD.rglob('*')if p.is_file()};assert names==set(expected)
        actual={k:sha(WORLD/k)for k in sorted(names)};assert actual==expected;return actual
    before_files=inventory();nav_report=read(NAV/'report.json')
    archive_class=ROOT/'build/classes/java/main/com/projectseele/world/DeadSeaArchiveBlockR45.class'
    assert sha(archive_class)==ARCHIVE_CLASS_SHA,'Native archive inheritance needs the unchanged actual compiled block class'
    archive_shapes={s:b for s,b in read(ARCHIVE_NATIVE).items()if s.startswith('projectseele:dead_sea_archive[')}
    assert len(archive_shapes)==4 and {properties(s)['facing']for s in archive_shapes}=={'north','east','south','west'}
    assert len(archive_shapes['projectseele:dead_sea_archive[facing=north]'])==6
    graph=gzread(WORLD/'nerv_routes_r24.json.gz');nearest=gzread(NAV/'nearest_lift_paths_r44.after.json.gz')
    assert sha(WORLD/'nerv_routes_r24.json.gz')==nav_report['routes_sha256']==nearest['graph_sha256']
    coords=[tuple(n[:3])for n in graph['nodes']];null=[q for q,r in zip(coords,nearest['nodes'])if r is None]
    assert len(coords)==len(nearest['nodes'])==143080 and len(null)==527
    components=read(NAV/'unreached_floor_components.json');assert sum(r['nodes']for r in components)==527
    r21=read(WORLD/'spatial_contract_r21.json');rooms=read(WORLD/'spatial_contract_r23.json')['room_entries'];assert len(rooms)==50
    m=MeasuredWorld(WORLD)
    m.box((-74,-464,231),(138,-326,422));m.box((-44,-447,-295),(136,-348,1))
    for belt in r21['belts']:
        x,y,z=belt['origin'];length=belt['length'];m.box((x-2,y-1,z-2),(x+(length if belt['axis']=='x'else 3),y+5,z+(length if belt['axis']=='z'else 3)))
    for q in null:m.around(q,3)
    m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-72,-464,-295),(340,-310,625),selected_chunks=set(m.selected)))
    def full(q):
        q=tuple(q);tag=tags.get(q);return dict(pos=list(q),state=m.block(q),full_nbt=None if tag is None else tag.snbt())
    raw=ActualGeometry(m)
    def point(q):
        boxes=raw.boxes((q[0],q[1]-1,q[2]))
        if boxes is not None:
            for top in sorted({b[4]for b in boxes},reverse=True):
                if not .01<=top<=1.0:continue
                if all(any(b[0]<=x<=b[3]and b[2]<=z<=b[5]and abs(b[4]-top)<.001 for b in boxes)for x in(.25,.5,.75)for z in(.25,.5,.75)):
                    return [q[0]+.5,q[1]-1+top,q[2]+.5]
        return [q[0]+.5,q[1],q[2]+.5]
    classification=[]
    for q in null:
        x,y,z=q;cx=min((-12,30,72),key=lambda c:abs(x-c))
        if y==-394 and -263<=z<=-261 and abs(x-cx)<=17:kind='RETIRED_COMPLETE_FRONT_CROSSWAY_GRAPH_ROW';why='Original whole shelf relocated to three actual Z-267..-265 circulation rows; existing front guard retained'
        elif y==-394 and -260<=z<=-248 and abs(x-cx)<=16:kind='RETIRED_COMPLETE_FORWARD_SERVICE_SHELF_GRAPH_ROW';why='Original full forward shelves and well frames explicitly retired; rear boarding device uses Z-224..-216'
        elif q==(35,-329,341):kind='ACTUAL_CHAMBER_INSIDE_READER_OBJECT';why='Complete original inside tier3 reader and NBT remain; its actual outline is not a missing floor or permission to remove it'
        elif y==-329 and 25<=x<=35 and 341<=z<=347 and q!=(30,-329,345):kind='AUTHORIZED_CLOSED_CHAMBER_INTERIOR';why='Actual complete tier3 readers/200tick chamber gate owns access; fixed walls are retained'
        elif q==(30,-329,345):kind='KNOWN_NATIVE_ARCHIVE_OBJECT_OBSTRUCTION';why='Existing real native6-AABB north object/maxY1.31; frozen/current compiled block class byte-equal; old world shape library omitted4 facing keys. Retain archive and permission role'
        elif y==-329 and(x in(24,36)or z==348):kind='COMPLETE_CHAMBER_BOUNDARY_STALE_GRAPH_ROW';why='Current authored chamber perimeter, not a passage or wall deletion permit'
        elif q in{(64,-378,308),(64,-364,308)}:kind='ACTUAL_LIFT_OUTSIDE_CALL_FIXED_BACKING';why='Actual call button at X65/Y+1/Z308 is attached to this fixed support'
        elif q in{(98,-367,-213),(99,-367,-213)}:kind='WHOLE_TWO_LANE_MTR_PORT_BLOCKED_BY_GENERATOR';why='Pressure-cladding generator omitted actual native flat MTR public floor from full three-metre headroom protection'
        else:kind='UNRESOLVED_COMPLETE_COMPONENT';why='Requires actual source ownership before any construction'
        classification.append(dict(pos=list(q),classification=kind,reason=why,full_footprint=[full((x,Y,z))for Y in(y-1,y,y+1,y+2)],native_pass=False))
    counts=dict(collections.Counter(r['classification']for r in classification));assert counts.get('UNRESOLVED_COMPLETE_COMPONENT',0)==0
    print(json.dumps(dict(classified527=counts)),flush=True)
    # One generic detector examines every actual flat native belt cell in the
    # commissioned old transport ledger; substitutions are retained separately.
    belt_rows=[];blocked=[]
    for belt in r21['belts']:
        x,y,z=belt['origin'];actual=[];other=collections.Counter();issues=[]
        for distance in range(belt['length']):
            for lane in(0,1):
                q=(x+distance if belt['axis']=='x'else x+lane,y,z+lane if belt['axis']=='x'else z+distance);state=m.block(q)
                if not(state and state.startswith('mtr:escalator_step[')and properties(state).get('orientation')=='flat'):
                    other[state]+=1;continue
                p=[q[0]+.5,y+.9375,q[2]+.5];status=raw.standing(p)
                actual.append(dict(block=list(q),state=state,feet=p,status=status))
                if status!='STATIC_STANDING':
                    record=dict(belt=belt['id'],lane=lane,block=list(q),feet=p,status=status,whole_head=[full((q[0],Y,q[2]))for Y in range(y+1,y+4)])
                    issues.append(record);blocked.append(record)
        belt_rows.append(dict(source_contract=belt,actual_native_flat_cells=len(actual),other_current_complete_states=dict(other),obstructed=issues,
            native_direction_and_real_player_transport_pass=False,actual=actual))
    old_ops=gzread(OLD/'ops.json.gz');owner_ops={tuple(r['box'][:3]):r for r in old_ops if r['box'][:3]==r['box'][3:]}
    applied=read(OLD/'applied_20260930_182259_771171/receipt.json');assert applied['verified']is True
    source_members=upper_pressure_members();known_public=protected_public_columns(m,Geometry(m),(-45,-399,-294),(110,-347,-205))
    changes={};held=[]
    for row in blocked:
        for member in row['whole_head']:
            q=tuple(member['pos']);state=member['state'];op=owner_ops.get(q)
            if state in AIR:continue
            if q in source_members and source_members[q]==state and op and op['state']==state and op['extra']==['minecraft:air'] and q not in tags and q in known_public:
                changes[q]=dict(pos=list(q),before=state,after='minecraft:air',before_nbt=None,after_nbt=None,
                    owner='r45/restore_whole_native_MTR_pressure_port',source_owner=op['owner'],reason='Restore complete original two-lane public port below its retained overhead header; native belt state and full pressure frame remain')
            else:held.append(dict(belt=row['belt'],native_block=row['block'],member=member,reason='Foreign or other complete owner; no generic deletion permitted'))
    assert set(changes)=={(x,y,-213)for x in(98,99)for y in(-367,-366,-365)},('Repair scope changed',changes,held)
    class Image:
        def __init__(self,opened):self.world=WORLD;self.opened=opened
        def block(self,q):return self.opened.get(tuple(q),m.block(q))
        def get(self,x,y,z):return self.block(tuple(map(math.floor,(x,y,z))))
    after_geometry=ActualGeometry(Image({q:r['after']for q,r in changes.items()}));crossing=[]
    candidate_belt_blocked=[dict(belt=b['source_contract']['id'],block=c['block'],candidate_status=after_geometry.standing(c['feet']))
        for b in belt_rows for c in b['actual']if after_geometry.standing(c['feet'])!='STATIC_STANDING']
    assert not candidate_belt_blocked
    for x in(98,99):
        points=[point((x,-367,z))for z in range(-215,-210)]
        statuses=[after_geometry.standing(p)for p in points]
        assert all(s=='STATIC_STANDING'for s in statuses),(x,points,statuses)
        sweeps=[after_geometry.clear([a[0],max(a[1],b[1]),a[2]],target=[b[0],max(a[1],b[1]),b[2]])for a,b in zip(points,points[1:])]
        assert all(s=='CLEAR'for s in sweeps),(x,points,sweeps)
        crossing.append(dict(lane=x-98,actual_original_surface_points=points,native_use=False,before=raw.standing(points[2]),candidate=after_geometry.standing(points[2]),
            higher_actual_endpoint_datum_horizontal_body_sweeps=sweeps,original_MTR_one_sixteenth_step_native_pass=False))
    regressions=[]
    for ident,lo,hi,expected_state in [('reported_wall105',(105,-395,-41),(105,-389,-34),'minecraft:air'),('reported_exit86',(86,-394,-270),(86,-391,-269),'minecraft:air')]:
        cells=[full((x,y,z))for x in range(lo[0],hi[0]+1)for y in range(lo[1],hi[1]+1)for z in range(lo[2],hi[2]+1)]
        assert all(c['state']==expected_state for c in cells);regressions.append(dict(id=ident,current_complete_cells=cells,current_matches_resolved_geometry=True,native_pass=False))
    low_foyer=[]
    for x in range(93,97):
        for z in range(-46,-31):
            q=(x,-442,z);low_foyer.append(dict(pos=list(q),point=point(q),status=raw.standing(point(q)),full=[full((x,y,z))for y in range(-445,-437)]))
    regressions.append(dict(id='reported_foyer95',original_complaint=[95,-442,-44],current_entire_four_column_south_extension=low_foyer,
        old_guard_plane_z=-43,old_plane_is_now_continuous_floor=all(r['status']=='STATIC_STANDING'for r in low_foyer if r['pos'][2]in(-44,-43,-42)),native_pass=False))
    # Full commissioned room footprints, all corners and all current bearing
    # cells, then actual same-floor chains from the existing measured table.
    navindex={q:i for i,q in enumerate(coords)};room_rows=[];coverage=[]
    for room in rooms:
        x0,x1,z0,z1=room['bounds'];feet=room['floor']+1;standing=[];status=collections.Counter();nearest_counts=collections.Counter();omitted=[]
        for x in range(x0,x1+1):
            for z in range(z0,z1+1):
                q=(x,feet,z);result=raw.standing(point(q));status[result]+=1
                if result!='STATIC_STANDING':continue
                standing.append(q);index=navindex.get(q);row=None if index is None else nearest['nodes'][index]
                if row is None:omitted.append(list(q))
                else:nearest_counts[str((row['nearest_landing'],row['requires_floor_transfer']))]+=1
        corners=[]
        for x,z in [(x0+1,z0+1),(x1-1,z0+1),(x0+1,z1-1),(x1-1,z1-1)]:
            q=(x,feet,z);index=navindex.get(q);route=None if index is None else nearest['nodes'][index]
            corners.append(dict(pos=list(q),full=[full((x,Y,z))for Y in(feet-1,feet,feet+1)],status=raw.standing(point(q)),actual_nearest_row=route))
        room_rows.append(dict(id=room['id'],purpose=room['purpose'],bounds=room['bounds'],feet=feet,entry=list(room['entry']),
            current_entry_full=[full((room['entry'][0],Y,room['entry'][2]))for Y in(feet-1,feet,feet+1)],whole_footprint_cells=sum(status.values()),statuses=dict(status),
            current_actual_bearing_nodes=len(standing),standing_not_in_current_derived_table=omitted,actual_same_floor_or_explicit_stair_roots=dict(nearest_counts),corners=corners,
            full_native_room_corner_to_current_lift_pass=False,source_label_encoding_not_rewritten=True))
        coverage+=standing
    # Include the complete current connecting floor at all eight commissioned
    # levels. Roofs, lift/cabin sweeps and other heights do not inherit this use.
    primary={r['feet']for r in room_rows};census=set(coverage)
    census.update(q for q in coords if q[1]in primary and -72<=q[0]<=136 and 233<=q[2]<=420)
    floor_rows=[];edges=[];supported_edge_blocks=[];directions=((1,0),(-1,0),(0,1),(0,-1));door_marker=read(WORLD/'.projectseele_command_sliding_doors_r01.json')
    controlled={tuple(q)for d in door_marker['doors']for q in d['aperture']}
    for q in sorted(census):
        p=point(q);status=raw.standing(p);index=navindex.get(q);nearest_row=None if index is None else nearest['nodes'][index]
        floor=m.block((q[0],q[1]-1,q[2]))
        disposition='CURRENT_ACTUAL_STATIONARY_BEARING'if status=='STATIC_STANDING'else'UNRESOLVED_CURRENT_FLOOR_COMPONENT'
        if status!='STATIC_STANDING':
            if floor and floor.partition('[')[0].endswith('_stairs'):disposition='ACTUAL_SHAPED_STAIR_INTERFACE_NATIVE_REQUIRED'
            elif q in controlled and m.block(q)=='minecraft:barrier':disposition='ACTUAL_REGISTERED_CLOSED_SLIDING_DEVICE'
            elif q in{(64,-378,308),(64,-364,308)}:disposition='ACTUAL_FIXED_LIFT_CALL_BACKING'
        floor_rows.append(dict(pos=list(q),status=status,feet=p,actual_nearest_row=nearest_row,room_or_current_commissioned_floor=True,
            disposition=disposition,current_full_footprint=[full((q[0],y,q[2]))for y in(q[1]-1,q[1],q[1]+1)]if status!='STATIC_STANDING'else None,native_pass=False))
        if status!='STATIC_STANDING':continue
        for dx,dz in directions:
            adjacent=(q[0]+dx,q[1],q[2]+dz);a=point(adjacent);other=raw.standing(a)
            if other=='STATIC_STANDING':
                if(dx,dz)in((1,0),(0,1)):
                    high=max(p[1],a[1]);sweep=raw.clear([p[0],high,p[2]],target=[a[0],high,a[2]])
                    if sweep!='CLEAR':
                        next_index=navindex.get(adjacent);next_row=None if next_index is None else nearest['nodes'][next_index]
                        emitted=bool(nearest_row and tuple(nearest_row['next'])==adjacent or next_row and tuple(next_row['next'])==q)
                        supported_edge_blocks.append(dict(a=list(q),b=list(adjacent),actual_native_a=p,actual_native_b=a,
                            full_body_sweep=sweep,current_derived_next_edge_emitted=emitted,complete_a=[full((q[0],y,q[2]))for y in(q[1]-1,q[1],q[1]+1)],
                            complete_b=[full((adjacent[0],y,adjacent[2]))for y in(q[1]-1,q[1],q[1]+1)],
                            disposition='EXISTING_PHYSICAL_SEPARATOR; actual emitted passage edge requires a separate contradiction review',construction_permitted=False,native_pass=False))
                continue
            if raw.clear(a)!='CLEAR':continue
            high=max(p[1],a[1]);sweep=raw.clear([p[0],high,p[2]],target=[a[0],high,a[2]])
            if sweep!='CLEAR':continue
            lower=[full((adjacent[0],q[1]-d,adjacent[2]))for d in range(1,5)]
            has_stair=any((r['state']or'').partition('[')[0].endswith('_stairs')for r in lower)
            reason='MEASURED_STAIR_DESCENT_NATIVE_REQUIRED'if has_stair else'COMPLETE_COMPONENT_EDGE_REQUIRES_PURPOSE_REVIEW'
            edges.append(dict(pos=list(q),normal=[dx,0,dz],adjacent=list(adjacent),adjacent_status=other,body_sweep=sweep,
                complete_current_edge=[full((q[0],Y,q[2]))for Y in range(q[1]-2,q[1]+3)],complete_adjacent_column=lower+[full((adjacent[0],Y,adjacent[2]))for Y in(q[1],q[1]+1,q[1]+2)],
                disposition=reason,construction_permitted=False,native_pass=False))
    forward=[changes[q]for q in sorted(changes)];inverse=[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt'])for r in forward]
    after_files=inventory();assert before_files==after_files
    out.mkdir(parents=True)
    jsonl(out/'forward.jsonl.gz',forward);jsonl(out/'inverse.jsonl.gz',inverse);jsonl(out/'positive_edit_mask.jsonl.gz',[r['pos']for r in forward])
    jsonl(out/'full_source_before_after_sha256.jsonl.gz',[dict(relative=k,before_sha256=before_files[k],after_sha256=after_files[k])for k in sorted(before_files)])
    write(out/'all527_actual_classification.json',classification);write(out/'all12_commissioned_belts_actual_width.json',belt_rows)
    write(out/'all50_room_floor_corner_lift_coverage.json',room_rows);write(out/'three_reported_regressions_actual.json',regressions)
    jsonl(out/'all8_complete_room_and_connector_floor_census.jsonl.gz',floor_rows);write(out/'all8_full_floor_exposed_edge_candidates.json',edges)
    write(out/'all8_actual_supported_point_physical_separators.json',supported_edge_blocks)
    write(out/'original_pressure_generator_owned6cells.json',[owner_ops[tuple(r['pos'])]for r in forward]);write(out/'native_two_lane_port_requests.json',crossing)
    write(out/'known_archive_native_inheritance.json',dict(native_shapes_file=str(ARCHIVE_NATIVE),native_shapes_sha256=sha(ARCHIVE_NATIVE),
        current_compiled_block_class=str(archive_class),current_and_frozen_class_sha256=ARCHIVE_CLASS_SHA,actual_old_native_capture_confirmed_by_City=True,
        actual4_facing_shapes=archive_shapes,source_world_old_library_not_mutated=True,classified_as_known_object_not_missing_floor=True,new_native_capture_run=False))
    report=dict(source_world=str(WORLD),complete_baseline_files=1736,complete_before_after_SHA_unchanged=True,null_nodes=527,null_components=453,classification_counts=counts,
        all12_current_native_belt_complete_width_checked=True,actual_native_belt_blocked_cells=len(blocked),candidate_same_detector_blocked_cells=len(candidate_belt_blocked),held_other_owner_members=held,
        repair_cells=len(forward),floor_belt_frame_or_BE_cells_changed=0,whole_three_metre_two_lane_port=True,retained_header_y=-364,
        original_applied_owner_receipt=str((OLD/'applied_20260930_182259_771171/receipt.json').resolve()),
        exact_full_before_NBT_and_inverse=True,closed_chamber75_retained=True,actual_original_call_backing2_retained=True,
        rooms_whole_footprints=50,room_footprint_cells=sum(r['whole_footprint_cells']for r in room_rows),actual_bearing_nodes=sum(r['current_actual_bearing_nodes']for r in room_rows),
        standing_room_points_missing_table=sum(len(r['standing_not_in_current_derived_table'])for r in room_rows),
        all8_whole_floor_and_connector_nodes=len(floor_rows),full_floor_exposed_edge_candidates=len(edges),edge_dispositions=dict(collections.Counter(r['disposition']for r in edges)),
        full_floor_physical_statuses=dict(collections.Counter(r['status']for r in floor_rows)),full_floor_purpose_dispositions=dict(collections.Counter(r['disposition']for r in floor_rows)),
        actual_supported_point_separator_edges=len(supported_edge_blocks),current_derived_next_edges_crossing_separator=sum(r['current_derived_next_edge_emitted']for r in supported_edge_blocks),
        world_written=False,Java_MC_Gradle_started=False,model_or_frozen_Java_changed=False,native_pass=False,user_art_pass=False,
        forward_sha256=sha(out/'forward.jsonl.gz'),inverse_sha256=sha(out/'inverse.jsonl.gz'),remaining='All physical room/lift/guard/device use, complete edges and native inherited archive shape/derived graph update remain separate; no graph null alone authorizes a repair')
    write(out/'report.json',report);print(json.dumps({k:v for k,v in report.items()if k not in('held_other_owner_members','remaining')},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args())
