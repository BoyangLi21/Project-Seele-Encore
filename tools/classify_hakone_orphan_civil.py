"""Classify whole obsolete civil assemblies by 26-neighbour 3D connectivity.

A component touching accepted public routes, active facilities, original transit,
actors, unknown materials or any capture edge is retained for separate review.
The survey alone never edits the world.
"""
from pathlib import Path
import argparse,json
import numpy as np
from scipy.ndimage import label,find_objects,binary_dilation,distance_transform_edt
from scipy.spatial import cKDTree
from author_hakone_lakefront import Editor
from query_blocks import AIR
from plan_ashi_landscape_r54 import NATURAL
from repair_hakone_funicular_civil import CIVIL
from repair_hakone_surface_ownership import load_grid,sampled
from hakone_earthworks import road_blocks

def run(a):
    C,A,O=a.source,a.authority,a.out;O.mkdir(exist_ok=False)
    x,z,X,Z=json.loads((C/'capture.json').read_text('utf8'))['bounds_xz'];lo,hi=a.lower,a.upper;shape=(hi-lo+1,Z-z+1,X-x+1);civil=np.zeros(shape,bool);foreign=np.zeros(shape,bool);soil=np.zeros(shape,bool);guard=np.zeros(shape,bool);e=Editor(C);yy=np.arange(lo,hi+1)[:,None,None]
    for file in (C/'source').glob('*.npz'):
     rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512);civil_names=np.array([s.split('[')[0]in CIVIL for s in r['names']]);foreign_names=np.array([s.split('[')[0]not in (CIVIL|NATURAL|{'minecraft:light','minecraft:barrier','minecraft:structure_void'})for s in r['names']]);soil_names=np.array([s.split('[')[0]in {'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:coarse_dirt'}for s in r['names']])
     for(cx,cz),v in zip(r['coords'],r['after']):
      ar=np.s_[:,cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];b=v[lo+128:hi+129];civil[ar]=civil_names[b];foreign[ar]=foreign_names[b];soil[ar]=soil_names[b]
     e.regions.clear()
    def box(q):
     l,y,t,r,Y,b=map(int,q);l=max(l,x);r=min(r,X);t=max(t,z);b=min(b,Z);y=max(y,lo);Y=min(Y,hi)
     if l<=r and t<=b and y<=Y:guard[y-lo:Y-lo+1,t-z:b-z+1,l-x:r-x+1]=True
    for r in json.loads((A/'catalog.json').read_text('utf8')):
     if 'occupied_bounds'in r:
      q=r['occupied_bounds'];box([q[0]-2,lo,q[2]-2,q[3]+2,q[4]+1,q[5]+2])
    for q in json.loads((A/'station-volumes.json').read_text('utf8')):box(q)
    for r in json.loads((A/'installed-public-spaces.json').read_text('utf8')):box(r.get('finite_bounds',r.get('bounds')))
    for r in json.loads((C/'capture.json').read_text('utf8'))['actors']:
     p=list(map(int,r['pos']));box([p[0]-10,p[1]-4,p[2]-10,p[0]+10,p[1]+10,p[2]+10])
    for r in json.loads((C/'devices.json').read_text('utf8')):
     p=r['position'];box([p[0]-2,p[1]-2,p[2]-2,p[0]+2,p[1]+2,p[2]+2])
    zz,xx=np.mgrid[z:Z+1,x:X+1]
    for candidate in a.accepted:
     d=load_grid(candidate/'plan/network.npz');walk=sampled(d,'walk',xx,zz).astype(bool);grade=sampled(d,'grade2',xx,zz);dist,idx=distance_transform_edt(~walk,return_indices=True);h=(grade[tuple(idx)]-1)//2
     guard|=(dist<=3)[None]&(yy>=h[None]-6)&(yy<=h[None]+8)
    pts=np.concatenate([r['points']for r in json.loads((A/'native-curves.json').read_text('utf8'))['trains']]);dist,idx=cKDTree(pts[:,[0,2]]).query(np.column_stack([xx.ravel()+.5,zz.ravel()+.5]));dist=dist.reshape(xx.shape);h=pts[idx,1].reshape(xx.shape)
    guard|=(dist<=6.5)[None]&(yy>=h[None]-10)&(yy<=h[None]+8)
    for q in a.preserve_box:box(q)
    groups,n=label(civil,np.ones((3,3,3),int));counts=np.bincount(groups.ravel());protected=set(np.unique(groups[guard]));attached=set(np.unique(groups[binary_dilation(foreign)]));faces=np.concatenate([groups[0].ravel(),groups[-1].ravel(),groups[:,0].ravel(),groups[:,-1].ravel(),groups[:,:,0].ravel(),groups[:,:,-1].ravel()]);cropped=set(np.unique(faces));objects=find_objects(groups);rows=[]
    for i,s in enumerate(objects,1):
     if s is None:continue
     q=[s[2].start+x,s[0].start+lo,s[1].start+z,s[2].stop+x-1,s[0].stop+lo-1,s[1].stop+z-1]
     rows.append(dict(id=i,cells=int(counts[i]),bounds=q,protected=i in protected,foreign_contact=i in attached,cropped=i in cropped))
    rows.sort(key=lambda r:-r['cells']);(O/'components.json').write_text(json.dumps(rows,indent=2),'utf8');np.savez_compressed(O/'components.npz',groups=groups,bounds=[x,lo,z,X,hi,Z],guard=guard)
    eligible=[r for r in rows if not(r['protected']or r['foreign_contact']or r['cropped'])]
    report=dict(source=str(C),authority=str(A),accepted=[str(c)for c in a.accepted],preserve_boxes=a.preserve_box,bounds_xyz=[x,lo,z,X,hi,Z],adjacency=26,total_components=len(rows),eligible_components=len(eligible),eligible_cells=sum(r['cells']for r in eligible))
    (O/'survey.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    
    

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','authority','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--accepted',type=Path,action='append',required=True)
    p.add_argument('--preserve-box',type=int,nargs=6,action='append',default=[])
    p.add_argument('--lower',type=int,default=32);p.add_argument('--upper',type=int,default=220)
    run(p.parse_args())
