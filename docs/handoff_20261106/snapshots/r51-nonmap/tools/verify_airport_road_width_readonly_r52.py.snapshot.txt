"""Independent current-shape readback of Root's complete airport junction.

Reads every 16 m cross-section, both old-road joints, real bearing cubes and
the station's retained 73 m public entrance. No World writes or native PASS.
"""
import json, math, hashlib
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from regional_voxels import canonical_state

BASE=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')
W=BASE/'WORLD_R52'
OUT=Path('.Codex/r52_runtime_close/roads_readonly/AIRPORT_AFTER_REPAIR_FULL_WIDTH_READBACK.json')
PAVING={'minecraft:black_concrete','minecraft:white_concrete','minecraft:gray_concrete','minecraft:smooth_stone',
    'minecraft:blackstone_slab','minecraft:smooth_stone_slab','projectseele:road_asphalt_slab',
    'projectseele:road_marking_slab','projectseele:period_station_floor','projectseele:nerv_floor_panel'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    plan=BASE/'final_map_audit/airport_road_intersection/full_width_at_grade_connection/PLAN.json'
    declaration=json.loads(plan.read_text('utf8'));assert declaration['world_written']
    shapes_file=W/'native_collision_shapes.json'
    shapes={canonical_state(k):v for k,v in json.loads(shapes_file.read_text('utf8')).items()}
    world=MeasuredWorld(W);world.box((343,63,94),(498,89,114))
    region_root=W/'dimensions/projectseele/geofront/region'
    files={region_root/f'r.{x//32}.{z//32}.mca' for x,z in world.selected}
    before={str(p):sha(p) for p in files};started=datetime.now(timezone.utc).isoformat()
    world.load();unknown=Counter();problems=[]
    def boxes(x,y,z):
        st=world.get(x,y,z)
        if st in AIR:return []
        result=shapes.get(st)
        if result is None:unknown[str(st)]+=1
        return result
    def top(x,z,near=None):
        result=[]
        for y in range(71,82):
            st=world.get(x,y,z)
            if st is None or st.partition('[')[0] not in PAVING:continue
            for b in boxes(x,y,z) or []:
                if b[0]<=1e-7 and b[3]>=1.-1e-7 and b[2]<=1e-7 and b[5]>=1.-1e-7:
                    result.append((y+b[4],y,st))
        if near is not None:result=[q for q in result if abs(q[0]-near)<=.501]
        return max(result) if result else None
    def clear(x,f,z,height=6.,half_width=.5):
        hits=[]
        # Include neighbor palettes: mod collision AABBs can protrude outside
        # their owning block. The target prism covers the whole column.
        for xx in range(math.floor(x-half_width)-1,math.floor(x+half_width-1e-7)+2):
            for zz in range(math.floor(z-half_width)-1,math.floor(z+half_width-1e-7)+2):
                for y in range(math.floor(f),math.ceil(f+height)):
                    for b in boxes(xx,y,zz) or []:
                        if (xx+b[0]<x+half_width-1e-7 and xx+b[3]>x-half_width+1e-7 and zz+b[2]<z+half_width-1e-7 and zz+b[5]>z-half_width+1e-7
                            and y+b[1]<f+height-1e-7 and y+b[4]>f+.001):
                            hits.append(dict(at=[xx,y,zz],state=world.get(xx,y,zz),box=b))
        return hits
    def bearing(x,y,z):
        bs=boxes(x,y-1,z)
        return bs is not None and any(b[0]<=1e-7 and b[3]>=1.-1e-7 and b[2]<=1e-7 and b[5]>=1.-1e-7 and abs(b[4]-1.)<1e-7 for b in bs)
    columns=[];tops={}
    for x in range(344,462):
        for z in range(97,113):
            q=top(x,z)
            if q is None:problems.append(dict(at=[x,z],kind='NO_RECOGNIZED_CURRENT_PAVING'));continue
            f,y,st=q;tops[x,z]=f;hit=clear(x+.5,f,z+.5)
            bb=bearing(x,y,z)
            row=dict(at=[x,f,z],floor_at=[x,y,z],floor_state=st,bearing_at=[x,y-1,z],bearing_state=world.get(x,y-1,z),
                actual_bearing=bb,whole_column_clear_6m=not hit,obstructions=hit)
            columns.append(row)
            if hit:problems.append(dict(at=row['at'],kind='ACTUAL_SIX_METRE_OBSTRUCTION',hits=hit))
            if not bb:problems.append(dict(at=row['at'],kind='NO_FULL_NATIVE_BEARING_BELOW_PAVING'))
    edges=[];maximum_step=0.
    for (x,z),f in tops.items():
        for dx,dz in ((1,0),(0,1),(1,1),(1,-1)):
            if (x+dx,z+dz) not in tops:continue
            rise=abs(tops[x+dx,z+dz]-f)
            maximum_step=max(maximum_step,rise)
            if rise>.501:edges.append(dict(from_pos=[x,f,z],to_pos=[x+dx,tops[x+dx,z+dz],z+dz],rise=rise))
    problems.extend(dict(q,kind='ADJACENT_NATIVE_PAVING_STEP_GT_HALF_BLOCK') for q in edges)
    cross=json.loads((BASE/'final_map_audit/airport_road_intersection/CANDIDATE.json').read_text('utf8'))
    crossing_fail=[dict(at=[x,z],feet=tops.get((x,z))) for x in range(386,393) for z in range(97,113) if tops.get((x,z))!=81.]
    problems.extend(dict(q,kind='ORIGINAL_NS_STREET_NOT_AT_81') for q in crossing_fail)
    retained=[]
    for x in range(458,461):
        for z in range(97,101):
            r=dict(at=[x,73,z],floor_state=world.get(x,72,z),body_hits=clear(x+.5,73,z+.5,1.8))
            r['exact_declared_floor']=r['floor_state']=='projectseele:period_station_floor'
            retained.append(r)
            if not r['exact_declared_floor'] or r['body_hits']:problems.append(dict(r,kind='RETAINED_UNDERPASS_NOT_CLEAR'))
    # Whole 3 m strip from the actual airport road endpoint into the ground
    # station concourse, independent of any broad station rectangle.
    station=[]
    for x in range(471,498):
        for z in range(93,96):
            q=top(x,z,73.)
            hit=clear(x+.5,73.,z+.5,1.8)
            row=dict(at=[x,73,z],actual_floor=q,body_hits=hit)
            station.append(row)
            if q is None or abs(q[0]-73.)>.01 or hit:problems.append(dict(row,kind='STATION_ENTRANCE_STRIP_REVIEW'))
    path_file=W/'quality_walk_cases.json';cases=json.loads(path_file.read_text('utf8'))
    walk=[q for q in cases if q['id'] in ('r28/nerv_airport/airport_road_walk','r28/nerv_airport/airport_road_walk/return')]
    assert len(walk)==2
    path_issues=[]
    for case in walk:
        for p in case['path']:
            x,f,z=p;q=top(math.floor(x),math.floor(z),f)
            if q is None or abs(q[0]-f)>.01 or clear(x,f,z,1.8):path_issues.append(dict(id=case['id'],at=p,actual_floor=q))
    # The entire edited 16 m width and joins were read. The old path continues
    # outside this finite window; do not silently call absent sections air.
    in_window_path_issues=[q for q in path_issues if 344<=q['at'][0]<498 and 94<=q['at'][2]<115]
    after={str(p):sha(Path(p)) for p in before};assert before==after,'World changed during independent read'
    result=dict(world=str(W),world_written=False,read_started_utc=started,read_completed_utc=datetime.now(timezone.utc).isoformat(),
        inputs=[dict(path=str(p),sha256=sha(p)) for p in (plan,shapes_file,path_file)],actual_region_sha256=before,
        full_width_z=[97,112],road_columns_checked=len(columns),edited_columns=116*16,joint_columns=2*16,
        max_adjacent_step_m=maximum_step,actual_columns=columns,
        joint_crosssections=[q for q in columns if q['at'][0] in (344,345,460,461)],
        retained_underpass_12=retained,station_3m_entrance_strip=station,metadata_paths=walk,
        metadata_path_in_window_issues=in_window_path_issues,problems=problems,unknown_shapes=dict(unknown),
        finite_width_shape_readback_passed=not problems and not unknown and not in_window_path_issues,
        native_walk_passed=False,native_vehicle_passed=False,road_art_passed=False,
        limits=['All 16 m edited columns and both unedited joints read against native AABBs.',
            'Every entire 1m column prism has 6m headroom, neighboring collision palettes and full native bearing below paving checks.',
            'Shape width and half-block steps do not prove actual vehicle wheel suspension or a native journey.',
            'Only finite current saved blocks; no dynamic entity/door/traffic or full original route test.'])
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(columns=len(columns),problems=len(problems),problem_kinds=dict(Counter(q['kind'] for q in problems)),
        unknown=dict(unknown),metadata_in_window_issues=len(in_window_path_issues),finite_shape_pass=result['finite_width_shape_readback_passed'])),flush=True)

if __name__=='__main__':main()
