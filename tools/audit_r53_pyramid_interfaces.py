"""Read complete registered pyramid rooms and existing active connector floors.

Retired nodes and conveyor bearing heights remain explicit; no diagnostic grants
construction permission. The NPZ is the query_blocks snapshot used by the stair audit.
"""
import argparse,json,gzip,functools,collections
from pathlib import Path
from audit_r53_pyramid_stair_treads import Frozen
from prepare_school_hakone_native_r45 import ActualGeometry
from r52_spatial_plan import PYRAMID
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
w=args.world;m=Frozen(args.source,w);g=ActualGeometry(m);g.boxes=functools.lru_cache(None)(g.boxes)
rooms=json.loads((w/'spatial_contract_r23.json').read_text(encoding='utf8'))['room_entries'];ys={r['floor']+PYRAMID.dy+1 for r in rooms}
graph=json.loads(gzip.decompress((w/'r53_personnel_walking_graph.json.gz').read_bytes()));nav=json.loads(gzip.decompress((w/'nerv_routes_r24.json.gz').read_bytes()));nodes=[tuple(n) for n in graph['nodes']];ix={q:i for i,q in enumerate(nodes)};edges={(a,c) for a,c,*_ in graph['walking_edges']};active={q for q,v in zip(nodes,nav['node_active']) if v}
assert nodes == [tuple(r[:3]) for r in nav['nodes']] and len(nodes) == len(nav['node_active'])
selected={q for q in active if q[1] in ys and -90<=q[0]<=150 and 207<=q[2]<=447};counts=collections.Counter();bad=[];drops=[];separators=[];sweeps=0
@functools.lru_cache(None)
def point(q):
 boxes=g.boxes((q[0],q[1]-1,q[2]))
 if boxes is not None:
  for top in sorted({r[4] for r in boxes},reverse=True):
   if .01<top<=1.0 and all(any(r[0]<=x<=r[3] and r[2]<=z<=r[5] and abs(r[4]-top)<.001 for r in boxes) for x in(.25,.5,.75) for z in(.25,.5,.75)):return(q[0]+.5,q[1]-1+top,q[2]+.5)
 return(q[0]+.5,q[1],q[2]+.5)
@functools.lru_cache(None)
def status(q):return g.standing(point(q))
room_results=[]
for room in rooms:
 x0,x1,z0,z1=room['bounds'];y=room['floor']+PYRAMID.dy+1;counts_room=collections.Counter();missing=[]
 for x in range(x0,x1+1):
  for z in range(z0,z1+1):
   q=(x,y,z);result=status(q);counts_room[result]+=1
   if result=='STATIC_STANDING' and q not in active:missing.append(q)
 entry=PYRAMID.block(room['entry']);room_results.append(dict(id=room['id'],purpose=room['purpose'],entry=entry,entry_status=status(entry),entry_active=entry in active,full_footprint_columns=sum(counts_room.values()),statuses=dict(counts_room),standing_without_active_navigation=missing))
for q in sorted(selected):
 s=status(q);counts[s]+=1
 if s!='STATIC_STANDING':
  states=[m.block((q[0],q[1]+d,q[2]))for d in(-1,0,1)]
  kind=('SHAPED_STAIR_INTERFACE' if (states[0]or'').partition('[')[0].endswith('_stairs') else
        'NATIVE_CLOSED_LIFT_DOOR' if states[1]=='projectseele:lift_door_interlock_r53' else 'UNRESOLVED')
  bad.append(dict(cell=q,status=s,classification=kind,states=states));continue
 p=point(q)
 for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
  a=(q[0]+dx,q[1],q[2]+dz);v=point(a);s=status(a);high=max(p[1],v[1]);start=(p[0],high,p[2]);finish=(v[0],high,v[2])
  if s=='STATIC_STANDING' and (dx,dz)in((1,0),(0,1)):
   sweeps+=1;cross=g.clear(start,target=finish)
   if cross!='CLEAR':separators.append(dict(a=q,b=a,status=cross,graph_edge_emitted=(ix[q],ix.get(a,-1))in edges or(ix.get(a,-1),ix[q])in edges,states=[m.block(q),m.block(a)]))
  if s!='NO_FULL_DATUM_BEARING' or g.clear(start,target=finish)!='CLEAR':continue
  lows=[d for d in(.5,1,1.5,2,2.5,3)if status((a[0],a[1]-d,a[2]))=='STATIC_STANDING']
  if lows and min(lows)<=.5:continue
  drops.append(dict(cell=q,to=a,lower=lows,states=[m.block((a[0],a[1]+d,a[2]))for d in(-4,-3,-2,-1,0,1)]))
report=dict(scope='Active commissioned room levels and current navigation connector cells in pyramid envelope; measured shaped bearing datum; no construction grant',source=str(args.source),rooms=room_results,nodes=len(selected),statuses=dict(counts),blocked_nodes=bad,body_sweeps=sweeps,separators=separators,drop_candidates=drops,unknown_shapes=sorted(g.unknown),world_written=False)
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('nodes',len(selected),'statuses',dict(counts),'sweeps',sweeps,'separators',len(separators),'drops',len(drops),'unknown',len(g.unknown));print('blocked',bad[:12]);print('drops sample',drops[:10])
