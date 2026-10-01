"""Whole authored building storeys, with real door states and stair interfaces.

Reports full floor islands and unguarded edges; it never fills unknown space.
Connected floor area is not a substitute for room use or visual acceptance.
"""
from pathlib import Path
from collections import Counter,deque
import argparse,json,math,time
from measure_world_r40 import MeasuredWorld,properties
from regional_voxels import canonical_state
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';WORLD=ART/'source_world_backup';OUT=ART/'building_floors'
DIR={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}

def main(extra_shapes=None,owners=None,only_ids=()):
    OUT.mkdir(parents=True,exist_ok=True);buildings=json.loads((owners or ART/'facility_catalogue/authored_ownership.json').read_text('utf8'))['buildings']
    if only_ids:buildings=[b for b in buildings if b['id'] in only_ids]
    stairs=json.loads((ART/'building_stairs/audit.json').read_text('utf8'))['components'];stairs_by={b['id']:[] for b in buildings}
    for s in stairs:
        if s['building'] in stairs_by:stairs_by[s['building']].append(s)
    shapes={canonical_state(k):v for k,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    if extra_shapes:shapes.update({canonical_state(k):v for k,v in json.loads(extra_shapes.read_text('utf8')).items()})
    unknown=set();records=[];started=time.monotonic()
    def boxes(state):
        if state is None:return None
        if state.partition('[')[0] in AIR|{'minecraft:light'}:return []
        prop=properties(state)
        if 'hinge' in prop and prop.get('open')=='false':state=state.replace('open=false','open=true')
        if state not in shapes:unknown.add(state);return None
        return shapes[state]
    for index,b in enumerate(buildings):
        lo,hi=b['planned_bounds'];x0,y0,z0=lo;x1,y1,z1=hi;w=MeasuredWorld(WORLD);w.box((x0-3,y0-5,z0-3),(x1+3,y1+1,z1+3));w.load()
        def clear(x,y,z):
            for xx in range(math.floor(x-.3),math.floor(x+.3)+1):
                for zz in range(math.floor(z-.3),math.floor(z+.3)+1):
                    for yy in (y,y+1):
                        bs=boxes(w.get(xx,yy,zz))
                        if bs is None:return False
                        if any(xx+q[0]<x+.3 and xx+q[3]>x-.3 and zz+q[2]<z+.3 and zz+q[5]>z-.3 and yy+q[1]<y+1.799 and yy+q[4]>y+.001 for q in bs):return False
            return True
        def bearing_height(x,y,z):
            for yy in range(y-1,y-5,-1):
                bs=boxes(w.get(x,yy,z))
                if bs is None:return None
                heights=[yy+q[4] for q in bs if q[0]<=.5<=q[3] and q[2]<=.5<=q[5] and yy+q[4]<=y+.001]
                if heights:return max(heights)
            return y-5
        floors=[]
        for feet in b['planned_floor_feet']:
            nodes={(x,z) for x in range(x0,x1+1) for z in range(z0,z1+1) if bearing_height(x,feet,z)==feet and clear(x+.5,feet,z+.5)}
            seeds=[];descent=set();interfaces=[]
            if b.get('entry') and b['entry'][1]==feet:
                ex,_,ez=b['entry'];candidates=[q for q in nodes if abs(q[0]-ex)+abs(q[1]-ez)<=2]
                for q in candidates:
                    if clear((q[0]+ex+1)/2,feet,(q[1]+ez+1)/2):seeds.append(q)
                interfaces.append(dict(kind='authored_entry',pos=b['entry'],candidate_floor_cells=candidates))
            for flight in stairs_by[b['id']]:
                for lane in flight.get('lanes',[]):
                    for name in ('entry','exit'):
                        q=lane[name]
                        if q[1]!=feet:continue
                        cell=(math.floor(q[0]),math.floor(q[2]));seeds.append(cell);interfaces.append(dict(kind='stair_'+name,flight=flight['id'],lane=lane['lane'],pos=q))
                    if lane['exit'][1]==feet:
                        a,c=lane['entry'],lane['exit'];dx=int(math.copysign(1,c[0]-a[0])) if abs(c[0]-a[0])>.1 else 0;dz=int(math.copysign(1,c[2]-a[2])) if abs(c[2]-a[2])>.1 else 0
                        # Highest and next tread are an identified descending
                        # route, unlike an unguarded side of the stair opening.
                        descent.add((math.floor(c[0])-dx,math.floor(c[2])-dz,-dx,-dz))
            edges=[];adj={q:[] for q in nodes}
            for x,z in nodes:
                for dx,dz in DIR.values():
                    other=(x+dx,z+dz)
                    if not clear(x+.5+dx*.5,feet,z+.5+dz*.5):continue
                    if other in nodes:adj[x,z].append(other);continue
                    if not clear(other[0]+.5,feet,other[1]+.5):continue
                    height=bearing_height(other[0],feet,other[1])
                    if height is None or height>=feet-.6:continue
                    if (x,z,dx,dz) in descent:continue
                    edges.append(dict(from_pos=[x,feet,z],normal=[dx,0,dz],drop=feet-height,neighbour_floor=w.get(other[0],feet-1,other[1]),location='building_perimeter' if not (x0<=other[0]<=x1 and z0<=other[1]<=z1) else 'interior_floor_opening'))
            reached=set(q for q in seeds if q in nodes);queue=deque(reached)
            while queue:
                for q in adj[queue.popleft()]:
                    if q not in reached:reached.add(q);queue.append(q)
            remaining=nodes-reached;islands=[]
            while remaining:
                q=remaining.pop();group=[q];queue=deque([q])
                while queue:
                    for n in adj[queue.popleft()]:
                        if n in remaining:remaining.remove(n);group.append(n);queue.append(n)
                islands.append(dict(cells=len(group),bounds=[[min(q[0] for q in group),feet,min(q[1] for q in group)],[max(q[0] for q in group),feet,max(q[1] for q in group)]],positions=group))
            floors.append(dict(feet_y=feet,walkable_cells=len(nodes),reached_cells=len(reached),interfaces=interfaces,unreachable_islands=islands,unguarded_edges=edges,
                status='REVIEW_REQUIRED' if islands or edges or not reached else 'STATIC_CONNECTED_NATIVE_AND_VISUAL_PENDING'))
        records.append(dict(id=b['id'],dimension=b['dimension'],floors=floors,source_bounds=b['planned_bounds']))
        if index%20==0:print('Whole-storey scan',index+1,'of',len(buildings),flush=True)
    summary=dict(buildings=len(records),storeys=sum(len(b['floors']) for b in records),floor_statuses=dict(Counter(f['status'] for b in records for f in b['floors'])),unguarded_edges=sum(len(f['unguarded_edges']) for b in records for f in b['floors']),unreachable_islands=sum(len(f['unreachable_islands']) for b in records for f in b['floors']),unknown_shapes=sorted(unknown),seconds=time.monotonic()-started)
    (OUT/'audit.json').write_text(json.dumps(dict(summary=summary,buildings=records,scope='Full floor and every edge of all authored building storeys; hinged doors are evaluated open using measured native shapes. Candidate failures require actual use, full threshold and generator review. No broad geometry change is authorized by these findings alone.'),ensure_ascii=False,indent=2),'utf8');print(summary,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--shapes',type=Path);p.add_argument('--owners',type=Path);p.add_argument('--id',action='append',default=[]);p.add_argument('--world',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    if a.world:WORLD=a.world
    if a.out:OUT=a.out
    main(a.shapes,a.owners,a.id)
