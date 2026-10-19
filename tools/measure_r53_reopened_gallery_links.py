"""Recover missing route edges at the user's previously removed X=54 wall."""
import argparse,gzip,json
from pathlib import Path
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry

def run(world,out):
    graph=json.loads(gzip.decompress((world/'r53_personnel_walking_graph.json.gz').read_bytes()))
    coords=[tuple(p) for p in graph['nodes']];lookup={p:i for i,p in enumerate(coords)}
    edges={(a,b) for a,b,_ in graph['walking_edges']}
    measured=MeasuredWorld(world);measured.box((49,-557,368),(58,-453,376));measured.load();shape=Geometry(measured)
    proposed=[];held=[];checked=0
    for y in (-554,-541,-527,-513,-499,-485,-471,-457):
        for z in range(370,375):
            for x in (53,54):
                a=(x,y,z);b=(x+1,y,z)
                if a not in lookup or b not in lookup:continue
                i,j=lookup[a],lookup[b];checked+=1
                if (i,j) in edges and (j,i) in edges:continue
                if any(shape.standing(p)['status']!='STATIC_STANDING' for p in (a,b)) or not shape.edge_clear(a,b):continue
                states=[measured.get(p[0],p[1]-1,p[2]) for p in (a,b)]
                moving=any('escalator' in s or 'moving_walk' in s for s in states)
                for start,end,sign in ((a,b,1),(b,a,-1)):
                    if (lookup[start],lookup[end]) in edges:continue
                    allowed=True
                    if moving:
                        # The same flat run on both sides owns its direction.
                        # Never turn a counterflow conveyor into a two-way edge.
                        witnesses=[]
                        for anchor in (51,56):
                            u=(anchor,y,z);v=(anchor+sign,y,z)
                            if u not in lookup or v not in lookup:continue
                            if measured.get(u[0],y-1,z)!=states[0] or measured.get(v[0],y-1,z)!=states[0]:continue
                            witnesses.append((lookup[u],lookup[v]) in edges)
                        allowed=bool(witnesses) and all(witnesses)
                    if allowed:proposed.append(dict(a=list(start),b=list(end),floor_states=states,source='Existing registered public gallery across retired X54 wall'))
                if moving and not any(p['a'] in (list(a),list(b)) and p['b'] in (list(a),list(b)) for p in proposed):
                    held.append(dict(a=a,b=b,reason='Existing one-way conveyor rule retained'))
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(dict(world=str(world),checked_pairs=checked,connections=proposed,held=held,world_written=False),ensure_ascii=False,indent=2),'utf8')
    print('Checked',checked,'missing declared edges to restore',len(proposed),'conveyor boundaries retained',len(held))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.world,a.output)
