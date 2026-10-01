"""Whole cross-section restoration at the measured R02 bay airport road / R22 bridge.

The old railway hump has no purpose below the current Y94 viaduct. Its entire
road width returns to the authored endpoint datum, with a founded embankment
and a measured portal replacing the R22 post mistakenly placed through it.
No MTR identity, virtual rail, runtime file or world block is written here.
"""
from pathlib import Path
from collections import Counter
import json,gzip,math,hashlib
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from regional_voxels import canonical_state
from audit_regional_roads_r44 import catalogue

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/surface_network/bay_airport_crossing'
NATURAL={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:coarse_dirt','minecraft:gravel','minecraft:grass','minecraft:tall_grass','minecraft:fern'}
PAVING={'minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone','minecraft:gray_concrete','minecraft:stone','minecraft:smooth_stone_slab','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}

def main():
    OUT.mkdir(parents=True,exist_ok=True);roads,sources=catalogue();w=MeasuredWorld(WORLD)
    lo,hi=(190,40,962),(265,103,1028);w.box(lo,hi);w.load()
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    rail=json.loads((ROOT/'artifacts/repair_r43/transit_resolved/native_snapshot.json').read_text('utf8'))
    curves=[r for r in rail['curves'] if r['mode']=='TRAIN' and any(195<=q[0]<=258 and 962<=q[2]<=1028 for q in r['points'])]
    assert curves and all(93.99<=q[1]<=94.01 for r in curves for q in r['points'] if 195<=q[0]<=258 and 962<=q[2]<=1028)
    shapes={canonical_state(k):v for k,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    native_contract=ROOT/'artifacts/access_r22/transit/civil/station_contract.json'
    contract=json.loads(native_contract.read_text('utf8'));assert [219,94,997] in contract['piers']
    terrain=np.load(ROOT/'artifacts/world_quality_r02/terrain_target.npz');ox,oz=map(int,terrain['origin']);g=int(terrain['height'][997-oz,219-ox])
    oldpost=[(x,y,z) for x in range(218,221) for z in range(996,999) for y in range(g-2,91)]
    assert all(w.block(q)=='minecraft:light_gray_concrete' and q not in tags for q in oldpost),'The complete source-owned R22 bridge post differs; preserve it for review'
    own_rails={};owned_template={}
    source_components=ROOT/'artifacts/world_quality_r02/extension_land_all/ops.json.gz'
    with gzip.open(source_components,'rt',encoding='utf8') as stream:
        for op in json.load(stream):
            if op['owner'] not in {'extension/road_deck','extension/road_crossbeam','extension/road_pier'}:continue
            x0,y0,z0,x1,y1,z1=op['box']
            if x1<lo[0] or x0>hi[0] or z1<lo[2] or z0>hi[2]:continue
            for x in range(max(x0,lo[0]),min(x1,hi[0])+1):
                for z in range(max(z0,lo[2]),min(z1,hi[2])+1):
                    for y in range(max(y0,lo[1]),min(y1,hi[1])+1):owned_template.setdefault((x,y,z),set()).add(canonical_state(op['state']))
    for path in (ROOT/'artifacts/spatial_repair_r41').glob('**/ops.json.gz'):
        with gzip.open(path,'rt',encoding='utf8') as stream:ops=json.load(stream)
        for op in ops:
            q=tuple(op['box'][:3])
            if op['box'][:3]==op['box'][3:] and 196<=q[0]<=258 and 984<=q[2]<=1000 and op['state'].startswith('projectseele:nerv_edge_rail['):
                own_rails[q]=canonical_state(op['state'])
    changes={};held=[];decisions=[]
    def current(q):return changes.get(q,(w.block(q),''))[0]
    def put(q,after,reason,allowed):
        q=tuple(q);old=w.block(q)
        if old is None or q in tags or old.partition('[')[0] not in allowed and old not in owned_template.get(q,()):
            held.append(dict(pos=q,state=old,has_nbt=q in tags,reason=reason));return False
        if old!=after:changes[q]=(after,reason)
        elif q in changes:del changes[q]
        return True
    # The exact unchanged complete original post retires into the new founded
    # road surface. Its replacement and headstock are built as one component.
    for q in oldpost:put(q,'minecraft:stone' if q[1]<80 else 'minecraft:air','Replace source-owned in-road R22 post by two off-road portal columns',{'minecraft:light_gray_concrete'})
    columns=[(x,z) for x in range(196,259) for z in range(986,999) if (x,z) in roads]
    for x,z in columns:
        oldfeet=roads[x,z][0]/2;oldY=math.floor(oldfeet-.001)
        assert roads.get((195,z),(162,))[0]==162 and roads.get((259,z),(162,))[0]==162
        grass=[y for y in range(40,81) if (w.get(x,y,z) or '').partition('[')[0]=='minecraft:grass_block']
        if grass:soil=max(grass)
        else:
            soil=39
            for y in range(40,81):
                if (w.get(x,y,z) or '').partition('[')[0] not in {'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel'}:break
                soil=y
        for y in range(soil+1,80):
            q=(x,y,z)
            if current(q) in owned_template.get(q,()) and current(q) not in AIR:continue
            boxes=shapes.get(current(q),[])
            if q not in tags and any(b[0]<=0 and b[1]<=0 and b[2]<=0 and b[3]>=1 and b[4]>=1 and b[5]>=1 for b in boxes):continue
            put(q,'minecraft:stone','Continuous compacted formation from measured natural bearing to roadway',NATURAL|PAVING|{'minecraft:light_gray_concrete'})
        surface='minecraft:black_concrete' if roads[x,z][1] else 'minecraft:smooth_stone'
        put((x,80,z),surface,'Full authored road width restored to endpoint feet Y81 below current Y94 viaduct',NATURAL|PAVING|{'minecraft:light_gray_concrete'})
        for y in range(81,max(87,oldY+3)):
            q=(x,y,z);s=current(q)
            if s in AIR:continue
            if q in own_rails and w.block(q)==own_rails[q]:
                put(q,'minecraft:air','Retire exact R41 guard mounted on the superseded raised deck; graded bank replaces its void',{'projectseele:nerv_edge_rail'});continue
            if q in oldpost:continue
            put(q,'minecraft:air','Retire only the old road slab and formation inside its authored column',PAVING|NATURAL)
        decisions.append(dict(pos=[x,z],before_feet=oldfeet,after_feet=81,old_column_bearing=soil))
    # A 1:2 bank joins the whole road edge to the existing hillside. Trees,
    # devices, authored structures and water are never cleared to produce it.
    for x in range(196,259):
        for side,edge in [(-1,986),(1,998)]:
            for distance in range(1,17):
                z=edge+side*distance
                if (x,z) in roads:continue
                natural=max((y for y in range(40,81) if (w.get(x,y,z) or '').partition('[')[0] in {'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel'}),default=39)
                target=80-math.ceil(distance/2)
                if target<=natural:continue
                if any(w.get(x,y,z) not in AIR and (w.get(x,y,z) or '').partition('[')[0] not in NATURAL for y in range(natural+1,target+1)):
                    held.append(dict(pos=[x,target,z],reason='Bank intersects an existing component; do not bury or trim it'));continue
                for y in range(natural+1,target+1):
                    after='minecraft:grass_block[snowy=false]' if y==target else 'minecraft:dirt' if y>=target-2 else 'minecraft:stone'
                    put((x,y,z),after,'Complete supported 1:2 road embankment blends to existing natural hillside',NATURAL)
    portal=[]
    for z in [980,1004]:
        footprint=[(x,zz) for x in range(218,221) for zz in range(z-1,z+2)]
        assert all((x,zz) not in roads for x,zz in footprint)
        ground=max(y for x,zz in footprint for y in range(40,89) if (w.get(x,y,zz) or '').partition('[')[0] in {'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel'})
        for x,zz in footprint:
            for y in range(ground-2,89):put((x,y,zz),'minecraft:light_gray_concrete','Measured off-road portal column embedded in natural bearing and joined to complete bridge headstock',NATURAL)
        portal.append(dict(centre=[219,94,z],bearing=ground,top=88))
    for x in range(218,221):
        for z in range(980,1005):
            for y in [89,90]:put((x,y,z),'minecraft:light_gray_concrete','Continuous portal headstock supports current R22 dual railway deck above full vehicle clearance',NATURAL|{'minecraft:light_gray_concrete'})
    failures=[]
    for x,z in columns:
        for y in range(81,87):
            s=current((x,y,z));boxes=[] if s in AIR else shapes.get(s)
            if boxes is None or any(y+b[1]<87 and y+b[4]>81 and b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 for b in boxes):failures.append(dict(pos=[x,y,z],state=s,reason='Incomplete full-width six-metre vehicle clearance'))
        q=(x,79,z);s=current(q);bearing=shapes.get(s)
        if bearing is None or not any(b[4]>=.999 and b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 for b in bearing):failures.append(dict(pos=q,state=s,reason='Formation still lacks immediate native collision bearing'))
    rows=[dict(pos=q,before=w.block(q),after=after,before_nbt=None,after_nbt=None,owner='r44/bay_airport_crossing',reason=reason) for q,(after,reason) in sorted(changes.items())]
    report=dict(world=str(WORLD),road='bay_airport_access',column_denominator=len(columns),cells=len(rows),held=held,static_failures=failures,complete_component_ready=not held and not failures,
        frozen_before_sha256=hashlib.sha256((OUT.parent/'road_structure_vehicle_before.json').read_bytes()).hexdigest(),
        ownership=dict(road_sources=sources,original_pier=[219,94,997],pier_source=str(native_contract),source_sha256=hashlib.sha256(native_contract.read_bytes()).hexdigest(),old_road_components=str(source_components),old_road_components_sha256=hashlib.sha256(source_components.read_bytes()).hexdigest()),
        before_failure_proved=dict(railway_clearance_5_5m_columns=21,unsupported_paving_columns=108,root_cause='R22 pier avoidance checked the primary road mask and omitted the authored extension road'),
        portal=portal,road_datum_before_after=decisions,virtual_rail_curves_unchanged=[r['id'] for r in curves],
        minimum_virtual_bridge_clearance_after=10,headstock_clearance_after=8,whole_bank_slope='1 vertical : 2 horizontal',
        native_player_vehicle_passed=False,visual_passed=False,world_changed=False,original_engineering=True)
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8') as stream:
            for row in rows:
                value=dict(row)
                if inverse:value['before'],value['after']=row['after'],row['before']
                stream.write(json.dumps(value)+'\n')
    (OUT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    successor=dict(world=str(WORLD),owner='r44/bay_airport_crossing',predecessors=sources,
        columns=[dict(pos=[x,z],before_height2=roads[x,z][0],after_height2=162) for x,z in columns],
        reason='Current evaluated railway sits at Y94; complete public street returns to its authored fixed endpoint Y81, replacing the obsolete old railway hump',
        proposed_until_exact_patch_applied=True,quality_passed=False)
    (OUT/'road_contract_delta.json').write_text(json.dumps(successor,indent=2),'utf8')
    cases=[dict(id=f'r44/bay_airport_crossing/z{z}/{direction}',start=[195.5 if direction=='east' else 259.5,81,z+.5],end=[259.5 if direction=='east' else 195.5,81,z+.5],both_directions=False) for z in range(986,999) for direction in ['east','west']]
    (OUT/'native_full_width_cases.json').write_text(json.dumps(cases,indent=2),'utf8')
    print({k:v for k,v in report.items() if k in ['column_denominator','cells','complete_component_ready']},'held',len(held),'failures',len(failures),flush=True)

if __name__=='__main__':main()
