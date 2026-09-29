"""Every live TRAIN platform, joined to exact blocks rather than old build lists."""
import argparse,json,gzip,math
from pathlib import Path
from collections import Counter
from measure_world_r40 import MeasuredWorld,WORLD,ROOT,properties

OUT=ROOT/'artifacts/world_combat_r40/stations'

def edge_owners(point,state,platforms):
    """A facing platform edge belongs to the nearest rail on that side.

    The previous radius-only scan counted the next track's gates as this
    track's gates. Keep ties explicit instead of inventing an owner.
    """
    facing=properties(state).get('facing');normal={'east':(1,0),'west':(-1,0),'north':(0,-1),'south':(0,1)}.get(facing)
    if normal is None:return []
    x,y,z=point;found=[]
    for p in platforms:
        a,b=p['position1'],p['position2']
        if abs(a['y']-y)>1:continue
        if a['x']==b['x'] and normal[0] and min(a['z'],b['z'])<=z<=max(a['z'],b['z']):distance=(a['x']-x)*normal[0]
        elif a['z']==b['z'] and normal[1] and min(a['x'],b['x'])<=x<=max(a['x'],b['x']):distance=(a['z']-z)*normal[1]
        else:continue
        if 0<distance<=15:found.append((distance,p['id']))
    nearest=min((d for d,i in found),default=None)
    return [i for d,i in found if d==nearest]

def main(world=WORLD,out=OUT,snapshot=None):
    out.mkdir(parents=True,exist_ok=True)
    snapshot=snapshot or world/'native_transit_r28.json'
    native=json.loads(snapshot.read_text('utf8'));platforms=[p for p in native['platforms'] if p['transportMode']=='TRAIN']
    resolved={int(p['platform_id']):p for p in native.get('resolved_platforms',[])}
    stations=native['stations'];w=MeasuredWorld(world)
    for p in platforms:
        a,b=p['position1'],p['position2'];w.box((min(a['x'],b['x'])-18,a['y']-3,min(a['z'],b['z'])-18),(max(a['x'],b['x'])+18,a['y']+14,max(a['z'],b['z'])+18))
    w.load();rows=[]
    for p in platforms:
        a,b=p['position1'],p['position2'];x,z=(a['x']+b['x'])/2,(a['z']+b['z'])/2;y=a['y'];axis='x' if a['z']==b['z'] else 'z';low=min(a[axis],b[axis]);high=max(a[axis],b[axis])
        matches=[s for s in stations if min(s['position1']['x'],s['position2']['x'])<=x<=max(s['position1']['x'],s['position2']['x']) and min(s['position1']['z'],s['position2']['z'])<=z<=max(s['position1']['z'],s['position2']['z'])]
        title=resolved[p['id']]['station_name'] if p['id'] in resolved else min(matches,key=lambda s:abs(s['position2']['x']-s['position1']['x'])*abs(s['position2']['z']-s['position1']['z']))['name'] if matches else 'UNMAPPED'
        edges={};boards=[];excluded=[];unresolved=[]
        for offset in range(-15,16):
            if offset==0:continue
            cells=[]
            for u in range(low,high+1):
                X,Z=(u,int(z)+offset) if axis=='x' else (int(x)+offset,u)
                for Y in range(y-1,y+2):
                    s=w.get(X,Y,Z)
                    if s and s.startswith('mtr:platform['):
                        owners=edge_owners((X,Y,Z),s,platforms)
                        if len(owners)!=1:
                            unresolved.append(dict(pos=[X,Y,Z],state=s,candidate_platform_ids=owners));continue
                        if owners[0]!=p['id']:
                            excluded.append(dict(pos=[X,Y,Z],actual_platform_id=owners[0]));continue
                        lower=w.get(X,Y+1,Z);upper=w.get(X,Y+2,Z)
                        cells.append(dict(pos=[X,Y,Z],state=s,lower=lower,upper=upper))
                for Y in range(y+1,y+8):
                    s=w.get(X,Y,Z)
                    if s and s.startswith(('projectseele:station_departure_board','projectseele:nerv_direction_panel','mtr:railway_sign','mtr:route_sign')):boards.append([X,Y,Z,s])
            if cells:edges[str(offset)]=cells
        related=[dict(number=r['routeNumber'],name=r['name'],indices=[i for i,q in enumerate(r['routePlatformData']) if q['platformId']==p['id']]) for r in native['routes'] if any(q['platformId']==p['id'] for q in r['routePlatformData'])]
        counts=Counter(c['lower'].partition('[')[0] if c['lower'] else 'UNKNOWN' for e in edges.values() for c in e)
        rows.append(dict(id=p['id'],station=title,centre=[x,y,z],axis=axis,ends=[low,high],routes=related,edges=edges,boards=boards,lower_states=dict(counts),gates=sum(v for k,v in counts.items() if 'door' in k),excluded_neighbour_edges=excluded,unresolved_edge_owners=unresolved))
        print(title,p['name'],[x,y,z],'edges',[(k,len(v)) for k,v in edges.items()],'gates',rows[-1]['gates'],'boards',len(boards),dict(counts),flush=True)
    (out/'actual_platforms.json').write_text(json.dumps(dict(platforms=rows,rail_snapshot=str(snapshot),scope='All live TRAIN platforms; facing and nearest-rail edge ownership. Nearby board counts are discovery only. This does not certify halls, entrances, transfers or train door alignment.'),ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,default=WORLD);p.add_argument('--out',type=Path,default=OUT);p.add_argument('--snapshot',type=Path);args=p.parse_args();main(args.world,args.out,args.snapshot)
