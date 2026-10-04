"""Offline complete B2 east switchback candidate; immutable source only."""
from __future__ import annotations
import argparse,collections,difflib,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
from audit_pyramid_components_r45 import ROOT,WORLD,BASELINE,read,write,sha,jsonl
from measure_world_r40 import MeasuredWorld,properties
from prepare_school_hakone_native_r45 import ActualGeometry
from query_blocks import AIR,iter_block_entities

NORTH='minecraft:polished_andesite_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]'
SOUTH=NORTH.replace('north','south')
FLOOR='projectseele:nerv_floor_panel';FRAME='projectseele:nerv_structural_panel'
BARS='minecraft:iron_bars[east=false,north=true,south=true,waterlogged=false,west=false]'
CIVIL={FLOOR,FRAME,'minecraft:polished_deepslate','minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:white_concrete','minecraft:cyan_terracotta'}

def full_body_status(geom,a,b=None):
    b=a if b is None else b;y=max(a[1],b[1]);lo=[min(a[0],b[0])-.3,y+1e-6,min(a[2],b[2])-.3];hi=[max(a[0],b[0])+.3,y+1.8,max(a[2],b[2])+.3]
    for x in range(math.floor(lo[0]),math.floor(hi[0])+1):
        for Y in range(math.floor(lo[1]),math.floor(hi[1])+1):
            for z in range(math.floor(lo[2]),math.floor(hi[2])+1):
                boxes=geom.boxes((x,Y,z))
                if boxes is None:return 'UNKNOWN_NATIVE_SHAPE'
                if any(all((x,Y,z)[k]+c[k]<hi[k] and (x,Y,z)[k]+c[k+3]>lo[k]for k in range(3))for c in boxes):return 'BODY_OBSTRUCTION'
    return 'CLEAR'

def main(out):
    out=out.resolve();assert not out.exists() and not out.is_relative_to(WORLD)
    expected={r['relative']:r['sha256']for r in read(BASELINE)['files']};assert len(expected)==1736
    def inventory():
        files={p.relative_to(WORLD).as_posix():sha(p)for p in WORLD.rglob('*')if p.is_file()};assert files==expected;return files
    before_files=inventory()
    m=MeasuredWorld(WORLD);m.box((48,-464,295),(89,-441,321));m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(48,-464,295),(89,-441,321)))
    g=ActualGeometry(m);changes={};held=[];preserved=[]
    def full(q):return dict(pos=list(q),state=m.block(q),full_nbt=tags[q].snbt()if q in tags else None)
    def put(q,state,owner,allowed):
        q=tuple(q);old=m.block(q);assert old is not None
        if old==state:changes.pop(q,None);return
        assert q not in tags and old in allowed,('Foreign component',q,old,state,owner)
        assert not(63<=q[0]<=69 and 299<=q[2]<=305),'Live shaft perimeter/capture volume'
        assert not(64<=q[0]<=85 and 307<=q[2]<=311 and -450<=q[1]<=-448),'Retained upper public lift corridor and bearing'
        changes[q]=dict(pos=list(q),before=old,after=state,before_nbt=None,after_nbt=None,owner=owner)
    for i in range(6):
        y,z=-456-i,310-i
        assert m.block((59,y,z))==SOUTH and m.block((59,y-1,z))=='minecraft:polished_deepslate'
        for x in range(59,62):
            put((x,y,z),SOUTH,'r45/B2/east_lower_complete_flight',AIR|{SOUTH,FRAME})
            put((x,y-1,z),'minecraft:polished_deepslate','r45/B2/east_lower_complete_stringer',AIR|{'minecraft:polished_deepslate'})
    lower_repair=list(changes.values());assert len(lower_repair)==8
    for i in range(6):
        y,z=-456-i,310-i
        for x in range(59,62):
            for h in(1,2):
                put((x,y+h,z),'minecraft:air','r45/B2/lower_complete_stair_headroom',AIR|CIVIL|{'projectseele:clear_glass'})
    # The old upper axis intersects the installed eight-floor shaft and lobby.
    # Retire only actual original stairs outside that retained device domain.
    for i in range(7):
        y,z=-449-i,304+i
        for x in range(67,70):
            q=x,y,z
            for old_q,expected_old in[(q,NORTH),((x,y-1,z),'minecraft:polished_deepslate')]:
                if m.block(old_q)!=expected_old:
                    preserved.append(dict(**full(old_q),reason='Current coupled civil/shaft material is not the original retired flight part'));continue
                if 63<=x<=69 and 299<=z<=305:held.append(dict(**full(old_q),reason='Inside active shaft/domain; preserve existing coupled state'));continue
                put(old_q,'minecraft:air','r45/B2/retire_complete_obsolete_upper_treads_and_stringers',{expected_old})
    # New upper flight is wholly within the original stairs room, west of the
    # active shaft and its same-floor circulation. Both original entries stay.
    for i in range(7):
        y,z=-449-i,304+i
        for x in range(55,58):
            put((x,y,z),NORTH,'r45/B2/relocated_upper_complete_flight',AIR|CIVIL)
            put((x,y-1,z),'minecraft:polished_deepslate','r45/B2/relocated_upper_stringer',AIR|CIVIL)
            for h in(1,2):put((x,y+h,z),'minecraft:air','r45/B2/upper_full_height',AIR|CIVIL|{'projectseele:nerv_wall_panel','projectseele:clear_glass',BARS})
        for x in(54,58):
            for h in(-1,0):
                q=x,y+h,z
                if m.block(q).startswith('minecraft:polished_basalt['):preserved.append(dict(**full(q),reason='Original structural pipe/riser supports the boundary'));continue
                put(q,FRAME,'r45/B2/upper_guard_stringer',AIR|CIVIL|{BARS})
            q=x,y+1,z
            if m.block(q).startswith('minecraft:polished_basalt['):preserved.append(dict(**full(q),reason='Original whole pipe/riser is the existing boundary'));continue
            put(q,BARS,'r45/B2/upper_continuous_guard',AIR|CIVIL|{BARS,'projectseele:clear_glass'})
    for x in range(54,59):
        for z in range(311,315):
            for y,state in[(-457,FRAME),(-456,FLOOR)]:
                q=x,y,z
                if m.block(q).startswith('minecraft:polished_basalt['):preserved.append(dict(**full(q),reason='Original perimeter structural pipe retained'));continue
                put(q,state,'r45/B2/whole_middle_landing_bearing',AIR|CIVIL)
            if x==54:
                q=x,-455,z
                if m.block(q).startswith('minecraft:polished_basalt['):continue
                put(q,BARS,'r45/B2/middle_landing_outer_guard',AIR|{BARS})
    for z in range(311,315):
        for y in(-455,-454):
            put((58,y,z),'minecraft:air','r45/B2/retire_old_middle_internal_guard',AIR|{'projectseele:clear_glass',BARS})
        q=59,-455,z;old=m.block(q)
        if old.startswith('projectseele:nerv_edge_rail[')and properties(old).get('west')=='true':
            sides=properties(old);sides['west']='false'
            after='projectseele:nerv_edge_rail['+','.join(k+'='+sides[k]for k in sorted(sides))+']'if 'true'in sides.values()else'minecraft:air'
            put(q,after,'r45/B2/retire_only_obsolete_middle_west_guard_face',{old})
    # Keep three full walking rows. The fourth original bearing row carries
    # the complete outside screen; it is not a fourth walking lane.
    for x in range(55,70):
        for y in(-455,-454):
            put((x,y,314),'projectseele:clear_glass','r45/B2/middle_complete_south_boundary',AIR|{'projectseele:clear_glass',BARS})
    # R40's bypass roof shares the landing datum north/east of this platform.
    # Keep that roof outside circulation after the obsolete flight retires.
    north_rail='projectseele:nerv_edge_rail[east=false,north=true,south=false,west=false]'
    for x in range(62,70):
        q=x,-455,310;effective=changes.get(q,{}).get('after',m.block(q))
        if effective in AIR:put(q,north_rail,'r45/B2/middle_complete_north_roof_boundary',AIR|{NORTH})
    for z in range(311,315):
        for y in(-455,-454):
            put((70,y,z),'projectseele:clear_glass','r45/B2/middle_complete_east_roof_boundary',AIR|{'projectseele:clear_glass'})
    class Image:
        world=WORLD
        def block(self,q):return changes.get(tuple(q),{}).get('after',m.block(q))
        def get(self,x,y,z):return self.block(tuple(map(math.floor,(x,y,z))))
    candidate=ActualGeometry(Image())
    body=full_body_status
    lanes=[]
    for name,xs,facing in [('lower',range(59,62),'south'),('upper',range(55,58),'north')]:
        for x in xs:
            points=([[x+.5,-461,304.5]]if name=='lower'else[[x+.5,-455,311.5]])
            for z in(range(305,311)if name=='lower'else range(310,303,-1)):
                y=-456-(310-z)if name=='lower'else-449-(z-304)
                points+=[[x+.5,y+.5,z+(.1 if facing=='south'else .9)],[x+.5,y+1,z+(.6 if facing=='south'else .4)]]
            points+=[[x+.5,-455,311.5]]if name=='lower'else[[x+.5,-448,303.5]]
            states=[body(candidate,p)for p in points];sweeps=[body(candidate,a,b)for a,b in zip(points,points[1:])]
            assert all(s=='CLEAR'for s in states+sweeps),(name,x,states,sweeps)
            assert max(abs(a[1]-b[1])for a,b in zip(points,points[1:]))<=.5
            lanes.append(dict(flight=name,lane_x=x,points=points,candidate_full0p6x1p8_body=states,higher_datum_sweeps=sweeps,max_authored_half_step=.5,native_walk=False))
    # A whole old landing strip connects both flights at their actual datum.
    middle=[[x+.5,-455,z+.5]for z in range(311,314)for x in range(55,70)]
    middle_results=[(p,candidate.standing(p),body(candidate,p))for p in middle]
    assert all(s=='STATIC_STANDING'and b=='CLEAR'for p,s,b in middle_results),middle_results
    middle_sweeps=[(x,z,body(candidate,[x+.5,-455,z+.5],[x+1.5,-455,z+.5]))for z in range(311,314)for x in range(55,69)]
    assert all(s=='CLEAR'for x,z,s in middle_sweeps),[r for r in middle_sweeps if r[2]!='CLEAR']
    assert all(body(candidate,[x+.5,-455,311.5],[x+.5,-455,309.5])=='BODY_OBSTRUCTION'for x in range(62,70))
    assert all(body(candidate,[69.5,-455,z+.5],[71.5,-455,z+.5])=='BODY_OBSTRUCTION'for z in range(311,314))
    footprint=[full((x,y,z))for x in range(53,75)for y in range(-463,-442)for z in range(300,319)]
    before_after=inventory();assert before_after==before_files
    out.mkdir();forward=sorted(changes.values(),key=lambda r:r['pos']);inverse=[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt'])for r in forward]
    jsonl(out/'forward.jsonl.gz',forward);jsonl(out/'inverse.jsonl.gz',inverse);jsonl(out/'positive_edit_mask.jsonl.gz',[r['pos']for r in forward]);jsonl(out/'whole_component_before_state_NBT.jsonl.gz',footprint)
    jsonl(out/'source1736_before_after.jsonl.gz',[dict(relative=k,before_sha256=v,after_sha256=before_after[k])for k,v in sorted(before_files.items())])
    write(out/'all_six_full_width_half_step_requests.json',lanes);write(out/'original_lift_domain_held.json',held);write(out/'original_pipes_and_BE_preserved.json',dict(pipes=preserved,BE=[dict(pos=q,full_nbt=t.snbt())for q,t in tags.items()]));write(out/'lower_real_failure8.json',lower_repair)
    write(out/'report.json',dict(component='Whole B2 east two-flight stair and middle landing',source=str(WORLD),source1736_SHA_unchanged=True,changes=len(forward),lower_complete_flight_tread18=True,lower_missing_treads4_stringers4=True,new_upper_treads21=True,new_upper_axis=[55,57],retained_upper_axis_inside_lift_held=held,
        body_six_lanes_full0p6x1p8_static_clear=True,middle_landing_net_full3_rows15_columns=True,original_entry_datum=[-461,-448],live63_302_shaft_and_upper_same_floor_corridor_untouched=True,all_BE_untouched=True,original_upper_component_treads_and_stringers_retired_outside_active_domain=True,current_coupled_structural_states_preserved=True,
        native_walk=False,installed=False,world_written=False,Java_Gradle_MC_started=False,model_modified=False,forward_sha256=sha(out/'forward.jsonl.gz'),inverse_sha256=sha(out/'inverse.jsonl.gz')))
    print('Prepared complete B2 stair candidate',len(forward),'cells; no world/source/model writes.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out)
