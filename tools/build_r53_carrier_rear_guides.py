"""Fit rear guide hardware to measured source facets and native route samples.

Produces a private, uninstalled candidate. Native fixed supports and full door
sweeps must pass before its installation can be declared. No world writes.
"""
import argparse
import hashlib
import json
import math
import zipfile
from pathlib import Path

import numpy as np

FACES=np.array([0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5])
COLOUR=np.array([.36,.43,.48])
BASIS=np.diag([-1.,1.,-1.])


def rgb(xyz):
    return np.column_stack([np.asarray(xyz).reshape(-1,3),np.tile(COLOUR,(len(np.asarray(xyz).reshape(-1,3)),1))]).ravel().tolist()


def beam(a,b,width=.16):
    a,b=map(np.asarray,(a,b));z=b-a;z/=np.linalg.norm(z)
    x=np.cross(z,[0.,1,0])
    if np.linalg.norm(x)<.1:x=np.cross(z,[1.,0,0])
    x/=np.linalg.norm(x);y=np.cross(z,x)
    ring=np.array([-x-y,x-y,x+y,-x+y])*width/2
    return rgb(np.concatenate([a+ring,b+ring])[FACES])


def guide_frame(direction):
    z=np.asarray(direction);z=z/np.linalg.norm(z)
    x=BASIS[:,0]-z*np.dot(BASIS[:,0],z)
    assert np.linalg.norm(x)>.1
    x/=np.linalg.norm(x)
    return np.stack([x,np.cross(z,x),z],axis=1)


def reduce_knots(points,corners,tolerance=.00005):
    """Retain native samples; use geometric distance rather than index time."""
    keep={0,len(points)-1}
    def split(a,b):
        delta=points[b]-points[a];length=np.linalg.norm(delta)
        if b-a<2:return
        f=np.clip((points[a+1:b]-points[a])@delta/max(length*length,1e-20),0,1)
        error=np.max(np.linalg.norm(corners[a+1:b]-(corners[a]+(corners[b]-corners[a])*f[:,None,None]),axis=2),axis=1)
        largest=int(np.argmax(error))+a+1
        if length>8 or float(error.max())>tolerance:
            k=(a+b)//2 if length>8 and error.max()<=tolerance else largest
            keep.add(k);split(a,k);split(k,b)
    split(0,len(points)-1)
    return sorted(keep)


def build(jar,samples,output,hardware_only=False):
    with zipfile.ZipFile(jar) as archive:
        carrier_bytes=archive.read('assets/projectseele/mesh/carrier_mk2_r53.json')
        carrier=json.loads(carrier_bytes)
        old_bytes=archive.read('assets/projectseele/mesh/upright_outer_captured_r52.json')
        transfer_bytes=archive.read('assets/projectseele/mesh/outer_head_transfer_r53.json')
        old=json.loads(old_bytes);transfer=json.loads(transfer_bytes)
    body=np.asarray(carrier['parts']['body']).reshape(-1,3,8)[:,:,:3]
    assert carrier['source_triangles']==8727
    # These are measured rear-facing source facets, not inferred bounding boxes.
    selected=[('rear_l',7,-1),('rear_r',105,1)]
    mounts=[];parts=[]
    template={p['name']:p for p in old['parts']}
    template.update({p['name']:p for p in transfer['parts']+transfer['socket_overrides']})
    for name,index,side in selected:
        triangle=body[index];centre=triangle.mean(0)
        normal=np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0]);normal/=np.linalg.norm(normal)
        assert normal[2]>.99 and centre[0]*side>3 and centre[2]>13
        # Use the existing opposite-corner rail datum. Vertically translating
        # two rear rails through the tight grade bends cuts the upright load;
        # the rear welds reach the established rail heads through side arms.
        ball=np.asarray(old['mounts_root_local'][0 if side<0 else 1])
        mounts.append(dict(id=name,side=side,ball=ball.tolist(),source_body_triangle=index,
            actual_weld_triangle=triangle.tolist(),weld_area=float(np.linalg.norm(np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0]))/2)))
        # A finite patch contained inside the actual imported face, extruded
        # outward. The original carrier triangle itself is never altered.
        patch=centre+(triangle-centre)*.22;outer=patch+normal*.12
        wedge=np.concatenate([patch,outer]);faces=[0,2,1,3,4,5,0,1,4,0,4,3,1,2,5,1,5,4,2,0,3,2,3,5]
        parts.append(dict(name=name+'/source_pad',frame='ROOT',role='source_weld',triangles_rgb=rgb(wedge[faces])))
        points=[centre+normal*.12,np.array([centre[0],centre[1],15.35]),
            np.array([centre[0],4.,15.35]),np.array([ball[0]-side*2.,4.,15.35]),
            np.array([ball[0]-side*2.,ball[1],15.35]),
            np.array([ball[0]-side*2.,ball[1],ball[2]]),ball-np.array([side*.14,0,0])]
        for n,(a,b) in enumerate(zip(points,points[1:])):
            if n==3:continue
            # The fixed arm terminates outside the moving rod. Its bracket
            # welds to the inward sleeve face above the stowed cross-arm.
            if n==2:b=b-np.array([side*.18,0.,0.])
            if np.linalg.norm(a-b)>1e-6:parts.append(dict(name=name+'/mount/'+str(n),frame='LIFT' if n>=4 else 'ROOT',role='structure',triangles_rgb=beam(a,b)))
        # Keep the existing service-bay floor. A short telescopic stage stows
        # the low guide head above it for transfer, then lowers at the bank.
        axis=np.array([points[3][0],0.,points[3][2]])
        bracket=axis-np.array([side*.18,0.,0.])
        parts.append(dict(name=name+'/lift_bracket/vertical',frame='ROOT',role='structure',
            triangles_rgb=beam(bracket+[0.,4.,0.],bracket+[0.,4.8,0.],.12)))
        parts.append(dict(name=name+'/lift_bracket/weld',frame='ROOT',role='structure',
            triangles_rgb=beam(bracket+[0.,4.8,0.],axis+[-side*.08,4.8,0.],.08)))
        for n,(dx,dz) in enumerate(((.08,0),(-.08,0),(0,.08),(0,-.08))):
            a=axis+np.array([dx,3.8,dz]);b=axis+np.array([dx,8.25,dz])
            parts.append(dict(name=name+'/lift_sleeve/'+str(n),frame='ROOT',role='lift_stator',triangles_rgb=beam(a,b,.04)))
            # An open rectangular top collar joins all four guide strips.
            # Its bore retains the exact 0.12 m square rod section.
            a=axis+np.array([dx-(.08 if dz else 0),8.2,dz-(.08 if dx else 0)])
            b=axis+np.array([dx+(.08 if dz else 0),8.2,dz+(.08 if dx else 0)])
            parts.append(dict(name=name+'/lift_tie/'+str(n),frame='ROOT',role='lift_stator',triangles_rgb=beam(a,b,.04)))
        parts.append(dict(name=name+'/lift_rod',frame='LIFT',role='lift_rod',triangles_rgb=beam(points[4],axis+[0.,4.5,0.],.12)))
        original_ball=np.asarray(old['mounts_root_local'][0 if side<0 else 1])
        for key,p in template.items():
            if not key.startswith(f'outer/{side}/'):continue
            if p['frame']=='ROOT' and p['role']!='ball':continue
            values=np.asarray(p['triangles_rgb']).reshape(-1,6).copy()
            if p['role']=='ball':values[:,:3]+=ball-original_ball
            # The original long capture housing clips the inner rail at the
            # tight Hakone transition. Keep the contact pads and actuator,
            # but shorten this procedural housing to a 0.16 m shoe span.
            if p['role']=='capture_structure' and np.ptp(values[:,2])>.1:
                values[:,2]*=.4
            parts.append(dict(name=name+'/'+key.split('/',2)[2],frame='LIFT' if p['role']=='ball' else name,
                role=p['role'],triangles_rgb=values.ravel().tolist()))
    hardware=dict(schema='projectseele.r53.rear-guide-hardware.v1',carrier_sha256=hashlib.sha256(carrier_bytes).hexdigest(),
        mounts=mounts,parts=parts,rail_head_section=old['rail_head_section'],rail_web_section=old['rail_web_section'],
        runner_origin_from_ball_local=old['runner_origin_from_ball_local'],head_slide=transfer['retraction_metres'],
        capture_housing_span_m=.16,transfer_stow_lift_m=7.,source_hardware_sha256={
            'mesh/upright_outer_captured_r52.json':hashlib.sha256(old_bytes).hexdigest(),
            'mesh/outer_head_transfer_r53.json':hashlib.sha256(transfer_bytes).hexdigest()})
    output.mkdir(parents=True,exist_ok=False)
    (output/'hardware.json').write_text(json.dumps(hardware,separators=(',',':')),'utf8')
    if hardware_only:
        print('hardware triangles',sum(len(p['triangles_rgb'])//18 for p in parts));return
    native=json.loads(samples.read_text('utf8'));rails=[];sockets=[];reports=[]
    for leg in native['legs']:
        if '/exit' not in leg['leg']:continue
        source=leg['samples'];root=np.array([s['root'] for s in source]);direction=np.array([s['tangent'] for s in source]);distance=np.array([s['metres'] for s in source]);q=np.array([guide_frame(d) for d in direction])
        assert all(s['rotation']==[0.,1.,0.,0.] for s in source)
        for mount in mounts:
            ball=np.asarray(mount['ball']);origin=root+BASIS@ball-q[:,:,1]*.35
            # End all fixed steel below the existing outlet floor. Upper
            # followers slide off first while the lower pair still captures.
            ceiling=root[-1,1]-.3
            valid=np.where(origin[:,1]<=ceiling)[0];assert valid[0]==0
            last=int(valid[-1])
            roots=root[:last+1].copy();origins=origin[:last+1].copy();frames=q[:last+1].copy();metres=distance[:last+1].copy()
            if last==len(root)-1:
                # Continue only the measured vertical tail to its existing
                # floor underside, so the stopped rear head remains captured.
                extension=np.array([0.,ceiling-origin[last,1],0.])
                roots=np.concatenate([roots,[root[last]+extension]])
                origins=np.concatenate([origins,[origin[last]+extension]])
                metres=np.r_[metres,distance[last]+extension[1]]
            else:
                f=(ceiling-origin[last,1])/(origin[last+1,1]-origin[last,1])
                roots=np.concatenate([roots,[root[last]+(root[last+1]-root[last])*f]])
                origins=np.concatenate([origins,[origin[last]+(origin[last+1]-origin[last])*f]])
                metres=np.r_[metres,distance[last]+(distance[last+1]-distance[last])*f]
            frames=np.concatenate([frames,[q[last]]])
            assert np.linalg.norm(direction[last]-[0,1,0])<1e-8
            local=[]
            for section in (hardware['rail_head_section'],hardware['rail_web_section']):
                x,y,X,Y=section;local.extend([[x,y,0],[X,y,0],[X,Y,0],[x,Y,0]])
            corners=np.einsum('nij,kj->nki',frames,np.asarray(local))+origins[:,None,:]
            keep=reduce_knots(roots,corners);next_seat=0
            for interval,(ia,ib) in enumerate(zip(keep,keep[1:])):
                for k,component in enumerate(('head','web')):
                    vertices=np.concatenate([corners[ia,k*4:(k+1)*4],corners[ib,k*4:(k+1)*4]])
                    centre=vertices.mean(0);xyz=(vertices-centre).astype(np.float32).astype(float)
                    name=f'rear/{leg["leg"]}/{mount["id"]}/{interval}/{component}'
                    rails.append(dict(name=name,leg=leg['leg'],mount=mount['id'],component=component,
                        origin=centre.tolist(),triangles_rgb=rgb(xyz[FACES])))
                    if component=='web' and (metres[ib]>=next_seat or ib==keep[-1]):
                        tri=xyz[[0,1,5]]+centre;n=np.cross(tri[1]-tri[0],tri[2]-tri[0]);n/=np.linalg.norm(n)
                        sockets.append(dict(leg=leg['leg'],mount=mount['id'],rail_piece=name,weld_triangle=tri.tolist(),
                            bearing=tri.mean(0).tolist(),normal=n.tolist(),metres=float((metres[ia]+metres[ib])/2)))
                        next_seat=metres[ib]+12
            reports.append(dict(leg=leg['leg'],mount=mount['id'],native_samples=len(source),retained_knots=len(keep),
                ends_before_outlet_m=float(leg['length']-metres[-1]),fixed_top_y=float(corners[:,:,1].max()),outlet_y=float(root[-1,1])))
    (output/'unanchored-rails.json').write_text(json.dumps(dict(schema='projectseele.r53.rear-guide-rails.v1',
        directory=native['directory'],native_samples_sha256=hashlib.sha256(samples.read_bytes()).hexdigest(),
        hardware_sha256=hashlib.sha256((output/'hardware.json').read_bytes()).hexdigest(),supports_complete=False,
        pieces=rails,sockets=sockets,report=reports),separators=(',',':')),'utf8')
    print('mounts',len(mounts),'hardware triangles',sum(len(p['triangles_rgb'])//18 for p in parts),'rail pieces',len(rails),'supports to measure',len(sockets))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('jar','samples','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--hardware-only',action='store_true')
    a=p.parse_args();build(a.jar,a.samples,a.output,a.hardware_only)
