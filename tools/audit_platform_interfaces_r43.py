"""Actual owned platform strips, every gate pair and passenger-side approach."""
from pathlib import Path
from collections import Counter
import argparse,json
from measure_world_r40 import MeasuredWorld,properties
from regional_voxels import canonical_state
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43'
NORMAL={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}

def main(world,out):
    out.mkdir(parents=True,exist_ok=True)
    platforms=json.loads((ART/'station_edge_ownership/actual_platforms.json').read_text('utf8'))['platforms'];w=MeasuredWorld(world)
    for p in platforms:
        x,y,z=map(int,p['centre']);a,b=p['ends']
        w.box((a-2,y-2,z-18) if p['axis']=='x' else (x-18,y-2,a-2),(b+2,y+4,z+18) if p['axis']=='x' else (x+18,y+4,b+2))
    w.load();shapes={canonical_state(k):v for k,v in json.loads((world/'native_collision_shapes.json').read_text('utf8')).items()};unknown=set()
    def shape(s):
        if s is None:return None
        if s.partition('[')[0] in AIR|{'minecraft:light'}:return []
        if s not in shapes:unknown.add(s);return None
        return shapes[s]
    def clear(s,height):
        bs=shape(s);return bs is not None and not any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and b[1]<height and b[4]>.001 for b in bs)
    def bearing(s):
        bs=shape(s);return bs is not None and any(b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and .9<=b[4]<=1.01 for b in bs)
    objects=[]
    for p in platforms:
        issues=[];gates=[];strips=[];x,y,z=map(int,p['centre']);horizontal=p['axis']=='x'
        for off,cells in p['edges'].items():
            face=properties(cells[0]['state'])['facing'];dx,dz=NORMAL[face];fy=Counter(c['pos'][1] for c in cells).most_common(1)[0][0];missing=[]
            for u in range(p['ends'][0],p['ends'][1]+1):
                q=(u,fy,z+int(off)) if horizontal else (x+int(off),fy,u);base=w.block(q)
                if not base or not base.startswith('mtr:platform['):
                    row=dict(kind='missing_platform_strip',pos=q,state=base,above=[w.get(q[0],fy+i,q[2]) for i in (1,2)])
                    missing.append(row);issues.append(row);continue
                lower=w.get(q[0],fy+1,q[2]);upper=w.get(q[0],fy+2,q[2])
                if not lower.startswith('mtr:apg_door['):continue
                prop=properties(lower);good=upper.startswith('mtr:apg_door[') and properties(upper).get('half')=='upper' and properties(upper).get('side')==prop.get('side')
                if not good:issues.append(dict(kind='broken_vertical_gate_pair',pos=q,lower=lower,upper=upper))
                adjacent=[w.get(q[0]+k*dz,fy+1,q[2]+k*dx) for k in (-1,1)]
                if not any(s and s.startswith('mtr:apg_door[') and properties(s).get('facing')==face and properties(s).get('side')!=prop.get('side') for s in adjacent):issues.append(dict(kind='broken_horizontal_gate_pair',pos=q,lower=lower,adjacent=adjacent))
                rear=(q[0]-dx,fy+1,q[2]-dz);states=[w.get(rear[0],fy+i,rear[2]) for i in (0,1,2)]
                usable=bearing(states[0]) and clear(states[1],1) and clear(states[2],.8)
                if not usable:issues.append(dict(kind='blocked_or_unsupported_boarding_approach',pos=q,approach=rear,states=states))
                gates.append(dict(pos=q,approach=rear,approach_usable=usable))
            strips.append(dict(offset=int(off),facing=face,expected_cells=p['ends'][1]-p['ends'][0]+1,missing_cells=len(missing)))
        objects.append(dict(id=p['id'],station=p['station'],strips=strips,gates=gates,issues=issues))
    report=dict(world=str(world),platforms=objects,counts=dict(Counter(r['kind'] for p in objects for r in p['issues'])),unknown_shapes=sorted(unknown),
        scope='All 34 native TRAIN platforms, owned strips and every actual APG door. Static interface failures only; no claim of live train alignment, boarding, halls, exits or whole-station acceptance.')
    (out/'interfaces.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(report['counts'],'unknown shapes',len(unknown),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,default=ART/'source_world_backup');p.add_argument('--out',type=Path,default=ART/'platform_interfaces_before');a=p.parse_args();main(a.world,a.out)
