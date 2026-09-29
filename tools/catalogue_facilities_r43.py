"""Join native transport ownership, actual device NBT and physical components.

Counts below are review denominators, never quality passes. A station area's
empty `exits` list does not mean it has no physical entrances.
"""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,hashlib,json
import nbtlib

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';OUT=ART/'facility_catalogue'
FEATURES=ART/'object_inventory_v2';WORLD=ART/'source_world_backup'

def read(path):return json.loads(path.read_text('utf8'))
def jsonl(path):
    with gzip.open(path,'rt',encoding='utf8') as stream:
        for line in stream:yield json.loads(line)
def identity(kind,dimension,points):
    return kind+'-'+hashlib.sha256(json.dumps([dimension,sorted(points)],separators=(',',':')).encode()).hexdigest()[:16]
def bounds(points):return [[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]]
def in_box(point,box,margin=0):return all(a-margin<=q<=b+margin for q,a,b in zip(point,*box))
def review():return {k:'UNREVIEWED' for k in ('function','fresh_native','inherited','visual_self_review','user_approved','lifecycle','final_install')}

def components(rows,dimension):
    types=defaultdict(dict)
    for row in rows:
        if row[4] in ('stairs','moving_walks','doors','pedestrian_gate','vertical_access','fare_gate_or_ticket_fixture'):
            types[row[4]][tuple(row[:3])]=row
    result=[]
    for kind,points in types.items():
        while points:
            p,row=points.popitem();group=[row];stack=[p]
            while stack:
                p=stack.pop()
                # Diagonal stair steps touch by edge, not necessarily face.
                for dx,dy,dz in ((1,0,0),(-1,0,0),(0,0,1),(0,0,-1),(0,1,0),(0,-1,0),
                                  (1,1,0),(-1,1,0),(0,1,1),(0,1,-1),(1,-1,0),(-1,-1,0),(0,-1,1),(0,-1,-1)):
                    q=(p[0]+dx,p[1]+dy,p[2]+dz)
                    if q in points:group.append(points.pop(q));stack.append(q)
            coords=[r[:3] for r in group];lo,hi=bounds(coords)
            result.append(dict(id=identity(kind,dimension,coords),dimension=dimension,kind=kind,bounds=[lo,hi],
                raw_cells=group,states=dict(Counter(r[3] for r in group)),
                endpoint_candidates=[r[:3] for r in group if r[1] in (lo[1],hi[1])],
                interpretation='Physical connected component; adjacent independent devices may require splitting',review=review()))
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    native=read(ART/'transit_resolved/native_snapshot.json');all_components=[];tags=[];cells_by_dimension={}
    for file in FEATURES.glob('*_cells.jsonl.gz'):
        stem=file.name.removesuffix('_cells.jsonl.gz');census=read(FEATURES/(stem+'_census.json'));dim=census['dimension']
        rows=list(jsonl(file));cells_by_dimension[dim]=rows;all_components.extend(components(rows,dim))
        tags.extend(jsonl(FEATURES/(stem+'_block_entities.jsonl.gz')))
    by_platform={str(p['id']):p for p in native['platforms']};ownership=defaultdict(list)
    for row in native['resolved_platforms']:ownership[row['station_id']].append(row)
    stations=[]
    for area in native['stations']:
        sid=str(area['id']);box=bounds([[p[a] for a in ('x','y','z')] for p in (area['position1'],area['position2'])])
        platforms=[]
        for resolved in ownership[sid]:
            source=by_platform[resolved['platform_id']];platforms.append(dict(id=resolved['platform_id'],mode=resolved['mode'],
                endpoints=[[source['position1'][a] for a in ('x','y','z')],[source['position2'][a] for a in ('x','y','z')]],
                route_ids=resolved['route_ids'],review=review()))
        relevant=[r for r in cells_by_dimension.get('projectseele:geofront',[]) if in_box(r[:3],box)]
        associated=[c['id'] for c in all_components if c['dimension']=='projectseele:geofront' and any(in_box(p,box) for p in c['endpoint_candidates'])]
        stations.append(dict(id=sid,name=area['name'],bounds=box,platforms=platforms,native_exits=area['exits'],
            native_exits_interpretation='Metadata only; physical entrance discovery required',component_candidates=associated,
            actual_feature_cells=dict(Counter(r[4] for r in relevant)),
            entrance_ports=[],halls=[],fare_gate_ports=[],transfer_ports=[],boarding_interfaces=[],review=review(),
            unresolved=['Physical exterior ports, halls, fare gates, transfers and train door interfaces not yet certified']))
    lifts=defaultdict(list);hardware=[]
    for row in tags:
        if row['id']=='movingelevators:elevator_tile':
            x,y,z=row['position'];tag=nbtlib.parse_nbt(row['nbt']);info=tag.get('data',{})
            lifts[row['dimension'],x,z].append(dict(controller=row['position'],name=str(info.get('name','')),
                nbt=row['nbt'],review=review(),call_hardware_candidates=[],port=None))
        elif row['id'].startswith('movingelevators:'):hardware.append(row)
    elevator_objects=[]
    for (dim,x,z),stops in sorted(lifts.items()):
        for stop in stops:
            sy=stop['controller'][1]
            stop['call_hardware_candidates']=[h for h in hardware if h['dimension']==dim and abs(h['position'][1]-sy)<=3 and abs(h['position'][0]-x)<=20 and abs(h['position'][2]-z)<=20]
        elevator_objects.append(dict(id=f'{dim}/lift/{x}/{z}',dimension=dim,controller_column=[x,z],landings=sorted(stops,key=lambda p:p['controller'][1]),
            lifecycle=['outside_call','wait','door_open','threshold_cross','ride','arrive','exit','return','same_jvm_reload','cold_reload'],
            review=review(),unresolved=['Controller column is a grouping hypothesis until native shaft/car and controller link are checked']))
    plan=read(WORLD/'regional_plan.json')
    record=dict(source_world=str(WORLD),native_snapshot_sha256=hashlib.sha256((ART/'transit_resolved/native_snapshot.json').read_bytes()).hexdigest(),
        stations=stations,lifts=elevator_objects,planned_zones=[dict(plan=p,review=review()) for p in plan['zones']],
        physical_components_file='physical_components.json.gz',
        unassigned_components=[c['id'] for c in all_components if not any(c['id'] in s['component_candidates'] for s in stations)],
        status='INCOMPLETE catalogue: membership is evidence, not quality acceptance; discovery outside registered facilities continues')
    with gzip.open(OUT/'physical_components.json.gz','wt',encoding='utf8') as f:json.dump(all_components,f,ensure_ascii=False,separators=(',',':'))
    (OUT/'catalogue.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
    summary=dict(station_areas=len(stations),train_platforms=sum(p['mode']=='TRAIN' for s in stations for p in s['platforms']),
        air_interfaces=sum(p['mode']=='AIRPLANE' for s in stations for p in s['platforms']),
        empty_station_areas=[s['name'] for s in stations if not s['platforms']],lift_controller_columns=len(elevator_objects),
        elevator_landings=sum(len(e['landings']) for e in elevator_objects),physical_components=len(all_components),
        unassigned_components=len(record['unassigned_components']),quality_passed_objects=0)
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8');print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
