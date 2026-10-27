"""Measure rear-guide supports on existing native mechanical lining faces.

Only the declared carrier routes and their existing machine/shaft lining are
eligible. No new rooms, corridor cuts or world blocks are inferred or written.
The output remains a candidate until complete carrier/gate sweeps are checked.
"""
import argparse
import hashlib
import json
import itertools
from pathlib import Path
import numpy as np
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from build_r53_carrier_rear_guides import beam,rgb,FACES
from audit_r53_rear_guide_space import overlaps

LINING={'projectseele:nerv_shaft_panel','projectseele:nerv_machine_panel',
    'projectseele:nerv_structural_panel','projectseele:nerv_wall_panel',
    'projectseele:nerv_floor_panel','projectseele:nerv_machine_edge',
    'minecraft:black_concrete','minecraft:gray_concrete','minecraft:iron_block',
    'minecraft:polished_basalt[axis=y]'}


def box_mesh(lo,hi):
    x,y,z=lo;X,Y,Z=hi
    return rgb(np.array([[x,y,z],[X,y,z],[X,Y,z],[x,Y,z],
        [x,y,Z],[X,y,Z],[X,Y,Z],[x,Y,Z]])[FACES])


def ray_box(origin,direction,box,maximum=32):
    lo,hi=np.asarray(box).reshape(2,3);near=-np.inf;far=np.inf;axis=-1
    for i in range(3):
        if abs(direction[i])<1e-9:
            if origin[i]<lo[i] or origin[i]>hi[i]:return None
        else:
            a,b=sorted(((lo[i]-origin[i])/direction[i],(hi[i]-origin[i])/direction[i]))
            if a>near:near=a;axis=i
            far=min(far,b)
    if near<.0001 or near>maximum or near>far or axis<0:return None
    point=origin+direction*near
    for i in range(3):
        if i!=axis:
            if hi[i]-lo[i]<.13:return None
            point[i]=np.clip(point[i],lo[i]+.065,hi[i]-.065)
    normal=np.zeros(3);normal[axis]=-np.sign(direction[axis])
    return near,point,normal


def support_parts(origin,start,point,normal,length):
    thickness=min(.08,length*.4);width=min(.10,length*.3)
    centre=point+normal*thickness*.5;lo=centre-.06;hi=centre+.06;axis=int(np.argmax(np.abs(normal)))
    lo[axis]=min(point[axis],point[axis]+normal[axis]*thickness)
    hi[axis]=max(point[axis],point[axis]+normal[axis]*thickness)
    parts=[('strut',beam(start,point+normal*thickness,width)),('wall_pad',box_mesh(lo,hi))]
    if np.linalg.norm(start-origin)>1e-6:parts.append(('rear_standoff',beam(origin,start,.10)))
    return centre,parts


def parts_clear(parts,geometry):
    for _,values in parts:
        tri=np.asarray(values).reshape(-1,3,6)[:,:,:3]
        lo=np.floor(tri.min((0,1))).astype(int);hi=np.floor(tri.max((0,1))).astype(int)
        for cell in itertools.product(*(range(lo[i],hi[i]+1) for i in range(3))):
            shapes=geometry.boxes(cell)
            if shapes is None:return False
            for raw in shapes:
                box=np.asarray(raw)+np.tile(cell,2)
                if overlaps(tri,box[:3],box[3:]):return False
    return True


def anchor(world,source,output):
    doc=json.loads(source.read_text('utf8'));m=MeasuredWorld(world)
    for s in doc['sockets']:
        p=np.asarray(s['bearing']);q=p+np.asarray(s['normal'])*12
        m.box(tuple(np.floor(np.minimum(p,q)-[33,1,1]).astype(int)),tuple(np.floor(np.maximum(p,q)+[33,1,1]).astype(int)))
    m.load();g=ActualGeometry(m);supports=[];missing=[];blocked=[]
    for index,s in enumerate(doc['sockets']):
        if 'anchor' in s:continue
        origin=np.asarray(s['bearing']);direction=np.asarray(s['normal'])
        options=[]
        witnesses=[origin]
        if doc.get('support_missing'):
            tri=np.asarray(s['weld_triangle'])
            witnesses += [np.asarray(weight)@tri for weight in ((.35,.5,.15),(.35,.15,.5),(.35,.05,.6))]
        rays=[]
        for witness in witnesses:
            rays.extend([(witness,witness,direction,12),(witness,witness+direction*.15,np.array([1.,0,0]),32),(witness,witness+direction*.15,np.array([-1.,0,0]),32)])
        for witness,start,ray,maximum in rays:
            start_cell=tuple(np.floor(start).astype(int));start_shapes=g.boxes(start_cell)
            if start_shapes is None:continue
            if any(np.all(start>np.asarray(box[:3])+start_cell+1e-7) and
                   np.all(start<np.asarray(box[3:])+start_cell-1e-7) for box in start_shapes):continue
            cells=[]
            for distance in np.linspace(.08,maximum,int(maximum*20)+1):
                at=tuple(np.floor(start+ray*distance).astype(int))
                if not cells or cells[-1]!=at:cells.append(at)
            for cell in cells:
                state=m.block(cell);shapes=g.boxes(cell)
                if shapes is None:blocked.append(dict(socket=index,at=cell,state=state,reason='unknown native shape'));break
                if not shapes:continue
                hits=[]
                for box in shapes:
                    hit=ray_box(start,ray,np.asarray(box)+np.tile(cell,2),maximum)
                    if hit:hits.append(hit)
                if not hits:continue
                if state not in LINING and not state.startswith('projectseele:nerv_launch_armor['):
                    blocked.append(dict(socket=index,at=cell,state=state,reason='not existing mechanical lining'));break
                options.append((cell,state,min(hits,key=lambda x:x[0]),start,witness));break
        chosen=None
        for option in sorted(options,key=lambda x:x[2][0]):
            _,_,(length,point,normal),start,witness=option
            if doc.get('require_full_clearance') and not parts_clear(support_parts(witness,start,point,normal,length)[1],g):continue
            chosen=option;break
        if chosen is None:missing.append(dict(index=index,**s));continue
        cell,state,(length,point,normal),start,origin=chosen
        s['bearing']=origin.tolist()
        # Native pad stays outside its measured wall face; the beam terminates
        # on the pad face. All dimensions remain explicit finite surfaces.
        centre,parts=support_parts(origin,start,point,normal,length)
        for name,values in parts:
            data=np.asarray(values).reshape(-1,6);data[:,:3]-=centre
            supports.append(dict(name=s['rail_piece']+'/support/'+str(index)+'/'+name,leg=s['leg'],mount=s['mount'],
                component='support',origin=centre.tolist(),triangles_rgb=data.ravel().tolist()))
        s['anchor']=dict(at=list(map(int,cell)),state=state,bearing=point.tolist(),normal=normal.tolist(),
            pad_half_width=.06,strut_length=float(length))
    doc['pieces']+=supports;doc['supports_complete']=not missing
    doc['support_source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    doc['support_missing']=missing;doc['support_blocked']=blocked
    output.write_text(json.dumps(doc,separators=(',',':'),default=lambda x:x.item() if isinstance(x,np.generic) else x),'utf8')
    print('socket count',len(doc['sockets']),'anchored',len(doc['sockets'])-len(missing),'missing',len(missing),'blocked',len(blocked),flush=True)
    from collections import Counter
    print(Counter(r['state'] for r in blocked),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('world','source','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();anchor(args.world,args.source,args.output)
