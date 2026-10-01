"""Objectise every frozen road defect and carry conflicting authored uses explicitly.

This is a review catalogue, not an exclusion-based quality pass. A transferred
station/airport object remains pending its corresponding complete owner QA.
"""
from pathlib import Path
from collections import Counter,defaultdict,deque
import json,hashlib,math,argparse
import numpy as np

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/surface_network'
BEFORE=ART/'road_structure_vehicle_before.json'

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=BEFORE);p.add_argument('--output',type=Path,default=ART/'road_object_catalogue.json');args=p.parse_args()
    report=json.loads(args.input.read_text('utf8'));plan=json.loads((ROOT/'artifacts/world_quality_r02/road_plan.json').read_text('utf8'))
    additions_path=ART/'road_authority_additions.json';additions={tuple(r['pos']):r for r in json.loads(additions_path.read_text('utf8'))['columns']} if additions_path.exists() else {}
    extension=json.loads((ROOT/'artifacts/world_quality_r02/extension_plan.json').read_text('utf8'))
    stations=json.loads((ROOT/'artifacts/access_r22/transit/civil/station_contract.json').read_text('utf8'))['stations']
    station_authority=[]
    for i,s in enumerate(stations):
        cx,cy,cz=s['center'];half=s['half'];dx,dz=(half,15) if s['horizontal'] else (15,half)
        station_authority.append(dict(id=f'r22_station/{i}/{s["station"]}',bounds=[cx-dx,cz-dz,cx+dx,cz+dz],ground=s['ground'],rail_y=cy,
            public_entries=[r for r in s['walks'] if '/ground_access_' in r['id'] and not r['id'].endswith('/return')]))
    # Explicit original road segments distinguish public carriageways from the
    # legacy planner's foot approaches, which accidentally inherited carriage=True.
    ox,oz=-2960,-1200;nx,nz=4304,2864;vehicle=np.zeros((nz,nx),bool);foot=np.zeros_like(vehicle)
    def draw(a,b,width,mask):
        length=max(abs(b[0]-a[0]),abs(b[1]-a[1]));r=width//2
        for i in range(length+1):
            x,z=round(a[0]+(b[0]-a[0])*i/max(1,length))-ox,round(a[1]+(b[1]-a[1])*i/max(1,length))-oz
            mask[max(0,z-r):min(nz,z+r+1),max(0,x-r):min(nx,x+r+1)]=True
    for x,z,X,Z,width in plan['segments']:draw((x,z),(X,Z),width,vehicle)
    for road in extension['roads']:
        for a,b in zip(road['points'],road['points'][1:]):draw((a[0],a[2]),(b[0],b[2]),road['width'],foot if road.get('walkway') else vehicle)
    def owners(x,y,z):
        uses=[]
        if (x,z) in additions:uses.append(dict(owner=additions[x,z]['source_id'],status='AUTHORED_EXPANSION_COMPLETE_ROAD_QA_REQUIRED',reference='road_authority_additions.json / exact original positive pavement operations'))
        if 350<=x<=1350 and -177<=z<=86 and 63<=y<=124:uses.append(dict(owner='r21/nerv_airport',status='SUPERSEDED_OLD_ROAD_DATUM',actual_airport_feet=73,reference='tools/build_nerv_airport_r21.py / nerv_un_airports exact deployment'))
        for s in station_authority:
            a,b,c,d=s['bounds']
            if a<=x<=c and b<=z<=d and s['ground']<=y<=s['rail_y']+14:
                uses.append(dict(owner=s['id'],status='STATION_FOYER_OR_COMPONENT_REQUIRES_FULL_OWNER_QA',reference='artifacts/access_r22/transit/civil/station_contract.json'))
        ix,iz=x-ox,z-oz
        if 0<=ix<nx and 0<=iz<nz:
            if vehicle[iz,ix]:uses.append(dict(owner='authored_public_carriageway',status='COMPLETE_ROAD_SECTION_REVIEW_REQUIRED'))
            elif foot[iz,ix]:uses.append(dict(owner='authored_pedestrian_walkway',status='NATIVE_FOOT_APPROACH_REVIEW_REQUIRED'))
            elif (x,z) not in additions:uses.append(dict(owner='legacy_mask_role_unresolved',status='HOLD_SEMANTIC_WIDTH_RECONCILIATION'))
        elif (x,z) not in additions:uses.append(dict(owner='unknown_source_role',status='HOLD'))
        return uses
    raw=[]
    for row in report['physical_floor_issues']:raw.append(dict(row))
    for row in report['road_terrain_edges']:raw.append(dict(row,kind=row['status']))
    for row in report['all_width_height_jumps']:raw.append(dict(row,pos=row['from_pos'],kind='ALL_WIDTH_GRADE_JUMP'))
    for row in report['road_rail_interfaces']:
        if row['status']!='SEPARATED_NATIVE_CURVE_HEIGHT':raw.append(dict(row,kind='VIRTUAL_RAIL_SWEEP_CONFLICT'))
    indexed=defaultdict(lambda:defaultdict(list))
    for row in raw:
        x,y,z=row['pos'];row['authored_uses']=owners(x,y,z);indexed[row['kind']][x,z].append(row)
    objects=[]
    for kind,cells in sorted(indexed.items()):
        remaining=set(cells)
        while remaining:
            first=min(remaining);remaining.remove(first);queue=[first];group=[]
            while queue:
                x,z=queue.pop();group.append((x,z))
                for dx in (-1,0,1):
                    for dz in (-1,0,1):
                        if (x+dx,z+dz) in remaining:remaining.remove((x+dx,z+dz));queue.append((x+dx,z+dz))
            rows=[r for q in group for r in cells[q]];x0,z0=min(x for x,z in group),min(z for x,z in group);x1,z1=max(x for x,z in group),max(z for x,z in group)
            uses=sorted({r['owner'] for row in rows for r in row['authored_uses']})
            objects.append(dict(id=f'road_object/{kind}/{x0}/{z0}',kind=kind,bounds=[[x0,min(r['pos'][1] for r in rows),z0],[x1,max(r['pos'][1] for r in rows),z1]],columns=len(group),raw_events=len(rows),authored_uses=uses,
                status='PENDING_COMPLETE_COMPONENT_QA',quality_passed=False,events=rows))
    result=dict(world=report['world'],frozen_before_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),full_mask_columns=report['full_authority_columns'],measured_columns=report['measured_columns'],
        objects=objects,object_kinds=dict(Counter(r['kind'] for r in objects)),raw_event_kinds=dict(Counter(r['kind'] for r in raw)),station_authority=station_authority,
        quality_passed=0,world_written=False,unclassified_objects=sum('unknown_source_role' in r['authored_uses'] or 'legacy_mask_role_unresolved' in r['authored_uses'] for r in objects),
        caution='Ownership transfer and native shape classification do not erase a defect or confer a pass. Complete floor/stair/vehicle/shore sections and live/visual owner QA remain explicit.')
    args.output.write_text(json.dumps(result,ensure_ascii=False),'utf8')
    print({k:v for k,v in result.items() if k not in ['objects','station_authority','caution']},'objects',len(objects),flush=True)

if __name__=='__main__':main()
