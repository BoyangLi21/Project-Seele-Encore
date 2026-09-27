"""Every live TRAIN platform, joined to exact blocks rather than old build lists."""
import json,gzip,math
from pathlib import Path
from collections import Counter
from measure_world_r40 import MeasuredWorld,WORLD,ROOT,properties

OUT=ROOT/'artifacts/world_combat_r40/stations'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    native=json.loads((WORLD/'native_transit_r28.json').read_text());platforms=[p for p in native['platforms'] if p['transportMode']=='TRAIN']
    stations=[s for s in native['stations'] if s['transportMode']=='TRAIN'];w=MeasuredWorld()
    for p in platforms:
        a,b=p['position1'],p['position2'];w.box((min(a['x'],b['x'])-18,a['y']-3,min(a['z'],b['z'])-18),(max(a['x'],b['x'])+18,a['y']+14,max(a['z'],b['z'])+18))
    w.load();rows=[]
    for p in platforms:
        a,b=p['position1'],p['position2'];x,z=(a['x']+b['x'])/2,(a['z']+b['z'])/2;y=a['y'];axis='x' if a['z']==b['z'] else 'z';low=min(a[axis],b[axis]);high=max(a[axis],b[axis])
        matches=[s for s in stations if min(s['position1']['x'],s['position2']['x'])<=x<=max(s['position1']['x'],s['position2']['x']) and min(s['position1']['z'],s['position2']['z'])<=z<=max(s['position1']['z'],s['position2']['z'])]
        title=min(matches,key=lambda s:abs(s['position2']['x']-s['position1']['x'])*abs(s['position2']['z']-s['position1']['z']))['name'] if matches else 'UNMAPPED'
        edges={};boards=[]
        for offset in range(-15,16):
            if offset==0:continue
            cells=[]
            for u in range(low,high+1):
                X,Z=(u,int(z)+offset) if axis=='x' else (int(x)+offset,u)
                for Y in range(y-1,y+2):
                    s=w.get(X,Y,Z)
                    if s and s.startswith('mtr:platform['):
                        lower=w.get(X,Y+1,Z);upper=w.get(X,Y+2,Z)
                        cells.append(dict(pos=[X,Y,Z],state=s,lower=lower,upper=upper))
                for Y in range(y+1,y+8):
                    s=w.get(X,Y,Z)
                    if s and s.startswith(('projectseele:station_departure_board','projectseele:nerv_direction_panel','mtr:railway_sign','mtr:route_sign')):boards.append([X,Y,Z,s])
            if cells:edges[str(offset)]=cells
        related=[dict(number=r['routeNumber'],name=r['name'],indices=[i for i,q in enumerate(r['routePlatformData']) if q['platformId']==p['id']]) for r in native['routes'] if any(q['platformId']==p['id'] for q in r['routePlatformData'])]
        counts=Counter(c['lower'].partition('[')[0] if c['lower'] else 'UNKNOWN' for e in edges.values() for c in e)
        rows.append(dict(id=p['id'],station=title,centre=[x,y,z],axis=axis,ends=[low,high],routes=related,edges=edges,boards=boards,lower_states=dict(counts),gates=sum(v for k,v in counts.items() if 'door' in k)))
        print(title,p['name'],[x,y,z],'edges',[(k,len(v)) for k,v in edges.items()],'gates',rows[-1]['gates'],'boards',len(boards),dict(counts),flush=True)
    (OUT/'actual_platforms.json').write_text(json.dumps(dict(platforms=rows,rail_snapshot='native_transit_r28.json',scope='All live TRAIN platforms, including stations absent from the historical civil template'),ensure_ascii=False,indent=2),encoding='utf8')

if __name__=='__main__':main()
