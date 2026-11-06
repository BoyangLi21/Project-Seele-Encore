"""Join installed-engine service dimensions to current station block samples.

This is an initial station triage, not a proof of entrances, native passenger
boarding, train-model clearance or complete transfer paths. Operational
switchbacks need independent native topology and retained survey evidence.
"""
import argparse,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from query_blocks import AIR
from plan_hakone_station_inventory import point
from map_pipeline.station_sections import StationSections
from verify_hakone_network_candidate import PAVEMENT

def ident(value):return str(int(value)&0xffffffffffffffff)
def pair(row):return tuple(sorted((tuple(point(row,'position1')),tuple(point(row,'position2')))))
def rail_id(row):
    p=pair(row)
    return '-'.join(f'{int(v)&0xffffffffffffffff:016X}'for q in p for v in q)

def audit(a):
    d=json.loads(a.engine.read_text('utf8'));survey=json.loads(a.survey.read_text('utf8'))
    e=StationSections(a.source);curves={r['id']:r for r in d['curves']}
    resolved={ident(r['platform_id']):r for r in d['resolved_platforms']}
    services=defaultdict(list)
    for s in d['resolved_sidings']:
        if 'route_ids'not in s:raise ValueError('Siding lacks engine-resolved depot')
        for route in s['route_ids']:services[ident(route)].append(s)
    platforms=[];unknown_floors=Counter();degree=Counter();adjacent=defaultdict(list)
    for r in d['rails']:
        aa,bb=pair(r);adjacent[aa].append(bb);adjacent[bb].append(aa)
        for p in (aa,bb):degree[p]+=1
    def terminal_tail(start,previous):
        path=[start];distance=0
        while len(path)<32 and distance<=80:
            onward=[p for p in adjacent[start]if p!=previous]
            if not onward:return path
            if len(onward)!=1:return None
            nxt=onward[0];distance+=math.dist(start,nxt);previous,start=start,nxt;path.append(start)
        return None
    floors=PAVEMENT|{'minecraft:polished_andesite','minecraft:stone','minecraft:quartz_block','minecraft:smooth_quartz',
        'mtr:platform','projectseele:period_station_floor','projectseele:station_tactile_path','projectseele:station_tactile_warning'}
    def clear(s):
        return s is not None and(s.split('[')[0]in AIR|{'minecraft:light'}or(s.split('[')[0].endswith('_door')and not s.startswith(('minecraft:iron_door','mtr:'))))
    for p in d['platforms']:
        pid=ident(p['id']);r=resolved[pid];curve=curves.get(rail_id(p))
        if curve is None:raise ValueError('Platform has no exact installed native curve')
        use=[s for rid in r['route_ids']for s in services[ident(rid)]]
        if not use:raise ValueError('Retained platform has no resolved operating vehicles')
        length=max(s['vehicle_length']for s in use)
        role='passenger';role_proof={}
        if 'station_id'not in r:
            aa,bb=pair(p);matches=[s for s in survey['switchbacks']if s['passenger']is False and abs(s['rail_y']-aa[1])<.1
                and min(math.dist([aa[0],aa[2]],s['endpoint']),math.dist([bb[0],bb[2]],s['endpoint']))<6]
            directions=[]
            for depot in d['depots']:
                for path in depot['path']:
                    pa=tuple(point(path,'startPosition'));pb=tuple(point(path,'endPosition'))
                    if tuple(sorted((pa,pb)))==(aa,bb):directions.append((pa,pb))
            reversal=any((q,b)in directions for b,q in directions)
            tails=[q for q in(terminal_tail(aa,bb),terminal_tail(bb,aa))if q]
            if len(matches)==1 and tails and reversal:
                role='non-passenger switchback'
                role_proof=dict(name=matches[0]['name'],retained_survey_passenger=False,native_terminal_tail=tails,
                    native_saved_path_uses_both_directions=True,current_curve_endpoints=[aa,bb])
            else:role='unresolved operational platform'
        sides=[]
        if role=='passenger'and curve['mode']=='TRAIN':
            points=np.asarray(curve['points'],float)
            for sign in(-1,1):
                positions=[];passable=[];blocked=[]
                for index in range(3,max(3,len(points)-3)):
                    v=points[index];tangent=points[min(index+1,len(points)-1)]-points[max(0,index-1)]
                    n=np.asarray([-tangent[2],tangent[0]]);n/=np.linalg.norm(n)
                    options=[]
                    for off in(3,4,5,6):
                        x,z=map(math.floor,v[[0,2]]+n*sign*off);y=round(float(v[1]));floor=e.state(x,y,z)
                        if floor is None:blocked.append(dict(pos=[x,y,z],reason='uncaptured section'));continue
                        material=floor.split('[')[0]
                        if material not in floors and not material.endswith('_planks'):
                            if material not in AIR:unknown_floors[material]+=1
                            continue
                        if material.endswith('_stairs'):continue
                        if all(clear(e.state(x,y+i,z))for i in(1,2)):
                            options.append([x,y+(.5 if 'type=bottom'in floor else 1),z])
                    positions.append(index)
                    if options:passable.append(dict(sample=index,choices=options))
                sides.append(dict(side=sign,longitudinal_samples=len(positions),samples_with_clear_paved_position=len(passable),
                    clear_positions=passable,unknown_sections=blocked))
        platforms.append(dict(native_id=pid,name=p['name'],station=r['station_name'],
            native_station_id=ident(r['station_id'])if 'station_id'in r else None,
            mode=curve['mode'],role=role,role_proof=role_proof,length=curve['length'],vehicle_length=length,
            length_margin=curve['length']-length,saved_native_capacity_sufficient=curve['length']+1e-6>=length,
            sides=sides,boarding_or_transfer_verified=False))
    station_rows=[]
    for s in d['stations']:
        ps=[r for r in platforms if r['native_station_id']==ident(s['id'])]
        station_rows.append(dict(native_id=ident(s['id']),name=s['name'],passenger_platforms=len(ps),
            modes=sorted({r['mode']for r in ps}),capacity_short_platforms=sum(not r['saved_native_capacity_sufficient']for r in ps),
            no_direct_platform=not ps,access_and_transfer_complete=False))
    report=dict(stations=station_rows,platforms=platforms,
        existing_stations=len(station_rows),passenger_platforms=sum(p['role']=='passenger'for p in platforms),
        confirmed_nonpassenger_switchbacks=sum(p['role']=='non-passenger switchback'for p in platforms),
        unresolved_operational_platforms=sum(p['role']=='unresolved operational platform'for p in platforms),
        short_native_platforms=sum(not p['saved_native_capacity_sufficient']for p in platforms),
        nonpaved_or_unclassified_side_materials=dict(unknown_floors),native_engine_source=str(a.engine),
        measured_source=str(a.source),world_written=False,all_station_access_complete=False,
        scope='Native engine platform length versus actual consist length; exact saved nearby paving samples. Separate platform paths, doors, entrances, transfers and model envelopes remain required.')
    a.out.mkdir(exist_ok=False)
    (a.out/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print({k:report[k]for k in('existing_stations','passenger_platforms','confirmed_nonpassenger_switchbacks','unresolved_operational_platforms','short_native_platforms')},flush=True)
    for p in platforms:
        if not p['saved_native_capacity_sufficient']or(p['sides']and max(s['samples_with_clear_paved_position']for s in p['sides'])<max(s['longitudinal_samples']for s in p['sides'])):
            print(p['station'],p['name'],'margin',round(p['length_margin'],2),'side samples',[(r['samples_with_clear_paved_position'],r['longitudinal_samples'])for r in p['sides']],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('engine','source','survey','out'):p.add_argument('--'+name,type=Path,required=True)
    audit(p.parse_args())
