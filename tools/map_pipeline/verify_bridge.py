"""Read back complete bridge decks, land bearings and native train exclusions."""
import argparse,json
from pathlib import Path
from collections import deque
import numpy as np
from scipy.spatial import cKDTree
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from query_blocks import AIR
from map_pipeline.corridors import alignment
from map_pipeline.train_clearance import intersects


def main(a):
    design=json.loads((a.candidate/'authored-design.json').read_text('utf8'))
    trains=json.loads(a.rails.read_text('utf8'))
    native=np.asarray([p for r in trains for p in r['points']],float);tree=cKDTree(native[:,[0,2]])
    e=Editor(a.candidate);errors=[];bridges=[]
    for spec in design['streets']:
        if not spec.get('bridge'):continue
        boxes=np.asarray(spec['bridge']['train_boxes'],float)
        d=np.load(a.candidate/'earthworks'/(spec['id']+'.npz'))
        x,z,X,Z=map(int,d['bounds']);walk=d['walk'];span=d['bridge_span']&walk;floor,_=road_blocks(d['grade2'])
        deck=set();bearings=[set(),set()];s0,s1=spec['bridge']['along'];curve,along=alignment(spec)
        for iz,ix in np.argwhere(span):
            y=int(floor[iz,ix]);xx,zz=x+int(ix),z+int(iz)
            for yy in range(y-int(d['deck_depth']),y+1):
                pos=(xx,yy,zz)
                if e.state(*pos).split('[')[0]in AIR:errors.append(['deck hole',*pos])
                deck.add(pos)
            for dz,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                j,i=iz+dz,ix+dx
                if not walk[j,i] or span[j,i]:continue
                yy=int(floor[j,i]);px,pz=x+int(i),z+int(j)
                for h in range(min(int(d['old'][j,i]),yy)-1,yy):
                    if e.state(px,h,pz).split('[')[0]in AIR:errors.append(['abutment gap',px,h,pz])
                near=int(np.argmin(np.linalg.norm(curve[:,[0,2]]-[px,pz],axis=1)))
                side=int(along[near]>(s0+s1)/2)
                for h in range(yy-2,yy+1):bearings[side].add((px,h,pz))
        if not all(bearings):errors.append(['missing opposite land bearings',spec['id']])
        connected=deck|bearings[0]|bearings[1];visited=set();todo=deque([next(iter(deck))])
        while todo:
            p=todo.popleft()
            if p in visited:continue
            visited.add(p);xx,yy,zz=p
            for q in ((xx+1,yy,zz),(xx-1,yy,zz),(xx,yy+1,zz),(xx,yy-1,zz),(xx,yy,zz+1),(xx,yy,zz-1)):
                if q in connected and q not in visited:todo.append(q)
        if not deck<=visited or not all(b&visited for b in bearings):errors.append(['deck does not join both abutments',spec['id']])
        parapets=0;radius=spec['carriage_width']/2+spec.get('sidewalk_width',2)
        for n in range(1,len(curve)-1,4):
            if not s0+1<=along[n]<=s1-1:continue
            tangent=curve[n+1,[0,2]]-curve[n-1,[0,2]];tangent/=np.linalg.norm(tangent)
            normal=np.array([-tangent[1],tangent[0]])
            for sign in (-1,1):
                for outward in np.arange(0,2.01,.25):
                    xx,zz=np.rint(curve[n,[0,2]]+sign*normal*(radius+outward)).astype(int)
                    if not walk[zz-z,xx-x]:break
                yy=int(floor[zz-z,xx-x])+1
                if 'stone_brick_wall' not in e.state(int(xx),yy,int(zz)):errors.append(['missing outer parapet',int(xx),yy,int(zz)])
                parapets+=1
        changed=0
        for file in (a.candidate/'delta').glob('*.npz'):
            with np.load(file)as f:
                for k,(cx,cz)in enumerate(f['coordinates']):
                    lo,hi=f['ranges'][k:k+2];idx=f['indices'][lo:hi].astype(np.int64)
                    for j,at in enumerate(idx):
                        xx,yy,zz=int(cx*16+at%16),int(at//256-128),int(cz*16+at//16%16)
                        if not x<=xx<=X or not z<=zz<=Z:continue
                        before=str(f['palette'][f['before'][lo+j]]);after=str(f['palette'][f['after'][lo+j]])
                        nearby=tree.query_ball_point([xx+.5,zz+.5],2.5)
                        if any(native[i,1]-3<=yy+1 and yy<native[i,1]+.01 for i in nearby):
                            errors.append(['native rail bed changed',xx,yy,zz,before,after])
                        if after.split('[')[0]not in AIR and intersects(boxes,xx,yy,zz):
                            errors.append(['new solid intersects reserved train volume',xx,yy,zz,after])
                        changed+=1
        bridges.append(dict(id=spec['id'],full_width_span_columns=int(span.sum()),structural_deck_cells=len(deck),
                            connected_to_both_land_bearings=True,outer_parapet_samples=parapets,
                            checked_delta=changed,new_train_intrusions=0,rail_bed_changes=0))
    report=dict(errors=errors,bridges=bridges,scope='new bridge and changed approaches; preexisting train-mesh contacts remain separately recorded',
                rendered_vehicle_test=False)
    (a.candidate/'bridge-check.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report if len(errors)<8 else dict(errors=len(errors),examples=errors[:8])),flush=True)
    if errors:raise ValueError('Bridge readback failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--rails',type=Path,required=True)
    main(p.parse_args())
