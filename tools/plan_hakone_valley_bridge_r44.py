"""Complete original R02 road bridge component: foundation, frame, coping and guard.

Read-only authoring. The route and its full thirteen-column road datum remain
fixed; only the proven legacy bridge component and its measured bearing change.
"""
from pathlib import Path
from collections import Counter,deque
import json,gzip,hashlib,math
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/surface_network/hakone_valley_bridge'
SOURCE=ROOT/'artifacts/world_quality_r02/extension_land_all/ops.json.gz'
GUARD='minecraft:iron_bars[east=true,north=true,south=true,waterlogged=false,west=true]'
SOIL={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel'}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with gzip.open(SOURCE,'rt',encoding='utf8') as stream:ops=json.load(stream)
    piers=[o for o in ops if o['owner']=='extension/road_pier' and o['box'][0]==-2232 and -299<=o['box'][2]<=-216]
    assert len(piers)==4
    w=MeasuredWorld(WORLD);lo,hi=(-2243,35,-306),(-2221,95,-208);w.box(lo,hi);w.load()
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    proposed={};held=[];records=[];before_edges=[];post_components=[]
    def put(q,state,reason,allowed):
        before=w.block(q)
        if before is None or q in tags or before.partition('[')[0] not in allowed:
            held.append(dict(pos=q,state=before,full_nbt=tags[q].snbt() if q in tags else None,reason=reason));return
        if before!=state:proposed[q]=(state,reason)
    def soil_y(x,z,stop):
        candidates=[y for y in range(35,stop+1) if (w.get(x,y,z) or '').partition('[')[0] in SOIL]
        return max(candidates) if candidates else None
    for op in piers:
        x,y,z,X,Y,Z=op['box'];assert x==X and z==Z and op['state']=='minecraft:polished_basalt[axis=y]'
        states=[w.get(x,yy,z) for yy in range(y,Y+1)]
        if any(s!=op['state'] for s in states) or any((x,yy,z) in tags for yy in range(y,Y+1)):
            held.append(dict(pos=[x,y,z],reason='Complete original pier state or NBT differs; preserve the component'));continue
        actual=soil_y(x,z,y-1)
        if actual is None:held.append(dict(pos=[x,y,z],reason='Unmeasured natural pier bearing'));continue
        gap=y-actual-1
        for yy in range(actual+1,y):put((x,yy,z),op['state'],'Extend the complete unchanged original pier to its current measured natural bearing',AIR)
        post_components.append(dict(centre=[x,z],source_bottom=y,source_top=Y,current_bearing=actual,unsupported_bottom_gap=gap))
    # Three continuous longitudinal members join all existing transverse
    # frames and the four measured piers. Existing solid terrain stays intact.
    for x in [-2239,-2232,-2225]:
        for z in range(-299,-215):
            q=(x,78,z);old=w.block(q)
            if old and old.partition('[')[0] in SOIL:continue
            put(q,'minecraft:iron_block','Continuous structural girder joins the existing bridge deck, frames and founded piers',AIR|{'minecraft:iron_block','minecraft:polished_deepslate','minecraft:polished_basalt'})
    for op in piers:
        z=op['box'][2]
        for x in range(-2239,-2224):
            for yy in [77,78]:
                old=w.get(x,yy,z)
                if old and old.partition('[')[0] in SOIL:continue
                put((x,yy,z),'minecraft:iron_block','Complete transverse frame ties both guard copings and road width to the original founded pier',AIR|{'minecraft:iron_block','minecraft:polished_deepslate','minecraft:polished_basalt'})
    for x in [-2239,-2225]:
        for z in range(-299,-215):
            ground=soil_y(x,z,79)
            if ground is None:held.append(dict(pos=[x,80,z],reason='Unmeasured whole bridge roadside'));continue
            before=[w.get(x,y,z) for y in [79,80,81,82]]
            before_edges.append(dict(pos=[x,81,z],drop_to_current_natural=81-(ground+1),states=before))
            put((x,79,z),'minecraft:iron_block','Supported continuous guard coping connects vertically to the longitudinal bridge frame',AIR|{'minecraft:iron_block','minecraft:polished_deepslate','minecraft:stone','minecraft:dirt','minecraft:grass_block'})
            put((x,80,z),'minecraft:smooth_stone','Continuous bridge coping carries the entire existing guard, rather than leaving a suspended fence',AIR|{'minecraft:iron_block','minecraft:polished_deepslate','minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:smooth_stone'})
            for y in [81,82]:
                old=w.get(x,y,z)
                if old not in AIR and old!=GUARD:
                    held.append(dict(pos=[x,y,z],state=old,reason='Modified bridge guard or unrelated component is preserved'));continue
                put((x,y,z),GUARD,'Restore the complete guard on its new structural coping, including the source threshold gaps above the deep valley',AIR|{'minecraft:iron_bars'})
    failures=[]
    def current(q):return proposed.get(q,(w.block(q),''))[0]
    shapes={canonical_state(k):v for k,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    for z in range(-299,-215):
        for x in range(-2238,-2225):
            s=current((x,80,z));expected='minecraft:black_concrete' if -2236<=x<=-2228 else 'minecraft:smooth_stone'
            if s!=expected:failures.append(dict(pos=[x,80,z],state=s,reason='The established full road width/datum differs; do not silently repaint it'))
            for y in range(81,87):
                state=current((x,y,z));boxes=[] if state in AIR else shapes.get(state)
                if boxes is None or any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and y+b[1]<87 and y+b[4]>81 for b in boxes):failures.append(dict(pos=[x,y,z],state=state,reason='Full width six metre vehicle clearance is blocked or unknown'))
        for x in [-2239,-2225]:
            support=current((x,78,z))
            if current((x,80,z))!='minecraft:smooth_stone' or current((x,79,z))!='minecraft:iron_block' or support.partition('[')[0] not in SOIL|{'minecraft:iron_block'}:failures.append(dict(pos=[x,80,z],reason='Guard coping does not join the complete frame or natural abutment'))
    structural={(x,y,z) for x in range(-2238,-2225) for z in range(-299,-215) for y in [78,79]}
    structural.update(q for q,(s,_) in proposed.items() if s in {'minecraft:iron_block','minecraft:smooth_stone','minecraft:polished_basalt[axis=y]'})
    seeds={(o['box'][0],77,o['box'][2]) for o in piers};structural.update(seeds)
    live={q for q in structural if current(q).partition('[')[0] in SOIL|{'minecraft:iron_block','minecraft:polished_deepslate','minecraft:polished_basalt','minecraft:smooth_stone'}}
    reached=set(seeds);queue=deque(seeds)
    while queue:
        x,y,z=queue.popleft()
        for dx,dy,dz in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
            q=x+dx,y+dy,z+dz
            if q in live and q not in reached:reached.add(q);queue.append(q)
    unsupported=live-reached
    if unsupported:failures.append(dict(reason='A full structural frame cell has no path to the measured founded piers',cells=len(unsupported),example=min(unsupported)))
    native=json.loads((ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json').read_text('utf8'))
    railway_conflicts=[]
    for curve in native['curves']:
        if curve['mode']!='TRAIN':continue
        for xx,yy,zz in curve['points']:
            for q in proposed:
                if abs(xx-q[0]-.5)<4 and abs(zz-q[2]-.5)<4 and yy-3<q[1]+1 and yy+8>q[1]:railway_conflicts.append(dict(pos=q,curve=curve['id']));break
            if railway_conflicts:break
        if railway_conflicts:break
    if railway_conflicts:failures.append(dict(reason='Proposed component enters a current virtual railway envelope',hits=railway_conflicts))
    rows=[dict(pos=q,before=w.block(q),after=after,before_nbt=None,after_nbt=None,owner='r44/hakone_airport_access/valley_bridge',reason=reason) for q,(after,reason) in sorted(proposed.items())]
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8') as stream:
            for row in rows:
                value=dict(row)
                if inverse:value['before'],value['after']=row['after'],row['before']
                stream.write(json.dumps(value)+'\n')
    report=dict(world=str(WORLD),source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        route='hakone_airport_access',component_bounds=[[-2239,35,-299],[-2225,82,-216]],road_feet=81,road_columns=13*84,
        original_piers=post_components,measured_original_guard_edges=before_edges,source_gap_reason='Old generator guarded only where centre native<roadY-8. Actual exterior hillside drops 15-16m at Z-254/-253 although the centre threshold was false.',
        changed_cells=len(rows),held=held,static_failures=failures,complete_component_ready=not held and not failures,
        structural_frame_cells=len(live),frame_cells_connected_to_founded_piers=len(reached),native_virtual_railway_conflicts=railway_conflicts,
        world_written=False,native_collision_walk_passed=False,visual_passed=False,original_engineering=True,
        scope='Complete founded frame and guard-bearing coping over the documented four-pier bridge span; no natural valley filling or route/traffic identity edit')
    (OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    cases=[dict(id=f'r44/hakone_valley_bridge/x{x}/{direction}',start=[x+.5,81,-299.5 if direction=='south' else -214.5],end=[x+.5,81,-214.5 if direction=='south' else -299.5]) for x in range(-2238,-2225) for direction in ['south','north']]
    (OUT/'native_full_width_cases.json').write_text(json.dumps(cases,indent=2),'utf8')
    print({k:v for k,v in report.items() if k in ['road_columns','changed_cells','complete_component_ready']},'held',len(held),'failures',len(failures),flush=True)

if __name__=='__main__':main()
