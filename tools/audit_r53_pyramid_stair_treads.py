"""Inspect complete straight stair flights in the frozen actual pyramid.

Furniture and isolated stair-shaped decor remain unclassified; this reader
does not grant construction permission from passable space.
"""
import argparse,json,math
from pathlib import Path
from collections import Counter,deque
import numpy as np
from measure_world_r40 import properties
from prepare_school_hakone_native_r45 import ActualGeometry
from station_sign_readers_r44 import NORMAL

class Frozen:
    def __init__(self,path,world):
        d=np.load(path);self.a=d['states'];self.palette=d['palette'].tolist();self.o=d['origin'].tolist();self.world=world
    def get(self,x,y,z):
        i=(math.floor(y)-self.o[1],math.floor(z)-self.o[2],math.floor(x)-self.o[0])
        return self.palette[int(self.a[i])] if all(0<=q<s for q,s in zip(i,self.a.shape)) else None
    def block(self,q):return self.get(*q)

def run(source,world,out):
    m=Frozen(source,world);geometry=ActualGeometry(m)
    ids=[i for i,s in enumerate(m.palette) if s.partition('[')[0].endswith('_stairs') and properties(s).get('half')=='bottom' and properties(s).get('shape')=='straight']
    cells={}
    for y,z,x in np.argwhere(np.isin(m.a,ids)):
        q=(int(x)+m.o[0],int(y)+m.o[1],int(z)+m.o[2]);cells[q]=m.block(q)
    remaining=set(cells);flights=[];unclassified=[]
    while remaining:
        seed=remaining.pop();state=cells[seed];dx,dz=NORMAL[properties(state)['facing']];part={seed};queue=deque([seed])
        while queue:
            q=queue.popleft()
            for d in ((dz,0,-dx),(-dz,0,dx),(dx,1,dz),(-dx,-1,-dz)):
                p=tuple(q[k]+d[k] for k in range(3))
                # A change of stair material does not end a continuous flight.
                # Every admitted cell already has the same bottom/straight
                # shape; facing and one-block rise define this connection.
                if p in remaining and properties(cells[p])['facing']==properties(state)['facing']:
                    remaining.remove(p);part.add(p);queue.append(p)
        if len({q[1] for q in part})<3:
            unclassified.append(dict(cells=sorted(part),state=state));continue
        failures=[]
        for x,y,z in sorted(part):
            # A player's footprint rests on the upper half before the next
            # riser; the low half is less than a full footprint deep.
            p=(x+.5+.2*dx,y+1,z+.5+.2*dz)
            status=geometry.clear(p)
            if status!='CLEAR':
                lo=(p[0]-.29,p[1]+.015,p[2]-.29);hi=(p[0]+.29,p[1]+1.785,p[2]+.29);hits=[]
                for X in range(math.floor(lo[0]),math.floor(hi[0])+1):
                    for Y in range(math.floor(lo[1]),math.floor(hi[1])+1):
                        for Z in range(math.floor(lo[2]),math.floor(hi[2])+1):
                            at=(X,Y,Z);boxes=geometry.boxes(at)
                            if boxes is None or any(all(at[k]+b[k]<hi[k] and at[k]+b[k+3]>lo[k] for k in range(3)) for b in boxes):hits.append(dict(pos=at,state=m.block(at)))
                failures.append(dict(tread=[x,y,z],point=p,status=status,hits=hits))
        landings=[]
        lanes={}
        for q in part:lanes.setdefault(dz*q[0]-dx*q[2],[]).append(q)
        for lane in lanes.values():
            lane.sort(key=lambda q:q[1]);a,b=lane[0],lane[-1]
            for kind,p in (('lower',(a[0]+.5-1.1*dx,a[1],a[2]+.5-1.1*dz)),('upper',(b[0]+.5+1.1*dx,b[1]+1,b[2]+.5+1.1*dz))):
                landings.append(dict(kind=kind,point=p,status=geometry.standing(p)))
        flights.append(dict(state=state,materials=dict(Counter(cells[q] for q in part)),cells=len(part),bounds=[[min(q[k] for q in part) for k in range(3)],[max(q[k] for q in part) for k in range(3)]],rises=len({q[1] for q in part}),failures=failures,landings=landings))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(dict(source=str(source),flights=flights,unclassified=unclassified,unknown_shapes=sorted(geometry.unknown),world_written=False),ensure_ascii=False,indent=2),'utf8')
    print('Flights',len(flights),'treads',sum(r['cells'] for r in flights),'blocked flights',sum(bool(r['failures']) for r in flights),'unclassified',len(unclassified))
    for r in flights:
        if r['failures']:print(r['bounds'],'rises',r['rises'],'blocked',len(r['failures']),r['failures'][:1])
        bad=[v for v in r['landings'] if v['status']!='STATIC_STANDING']
        if bad:print('LANDINGS',r['bounds'],bad[:3])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.source,a.world,a.output)
