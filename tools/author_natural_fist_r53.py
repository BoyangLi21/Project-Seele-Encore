"""Author a closed-fist corrective from the continuous CC0 source hand."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import sys,json,argparse,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from scipy.spatial.transform import Rotation as R
from adapt_makehuman_hand_r45 import subdivide
from collections import Counter

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--jar',type=Path,required=True)
parser.add_argument('--makehuman',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();base=args.out;base.mkdir(parents=True,exist_ok=True);p=args.makehuman
rig=json.loads((p/'default.mhskel').read_text('utf8'))
wd=json.loads((p/'default_weights.mhw').read_text('utf8'))['weights']
v=[];faces=[];group=''
for l in (p/'base.obj').read_text('utf8').splitlines():
    if l.startswith('v '):v.append([float(x)for x in l.split()[1:4]])
    elif l.startswith('g '):group=l[2:]
    elif l.startswith('f ')and group=='body':faces.append([int(x.split('/')[0])-1 for x in l.split()[1:]])
v=np.array(v)
def head(n):return v[rig['joints'][rig['bones'][n]['head']]].mean(0)
def tail(n):return v[rig['joints'][rig['bones'][n]['tail']]].mean(0)
def unit(x):return x/np.linalg.norm(x)
names=[n for n in wd if n.endswith('.L')and n.startswith(('finger','metacarpal','wrist'))]
mass=np.zeros(len(v))
for n in names:
    for i,w in wd[n]:mass[i]+=w
faces=[f for f in faces if all(mass[i]>.3 for i in f)]
keep=sorted({i for f in faces for i in f});ix={old:i for i,old in enumerate(keep)}
w=np.zeros((len(keep),len(names)))
for j,n in enumerate(names):
    for old,weight in wd[n]:
        if old in ix:w[ix[old],j]+=weight
w[:,names.index('wrist.L')]+=np.maximum(0,1-w.sum(1));w/=w.sum(1)[:,None]
points,quads,w=subdivide(v[keep],[[ix[i]for i in f]for f in faces],w)
tri=np.array([[f[0],f[i],f[i+1]]for f in quads for i in range(1,len(f)-1)])
edges=Counter(tuple(sorted((a,b)))for f in quads for a,b in zip(f,f[1:]+f[:1]))
boundary=[(a,b)for f in quads for a,b in zip(f,f[1:]+f[:1])if edges[tuple(sorted((a,b)))]==1]
cache={}

def source_matrix(n):
    if n in cache:return cache[n]
    if n=='wrist.L' or n.startswith('metacarpal'):m=np.eye(4)
    else:
        parent=rig['bones'][n]['parent'];pm=source_matrix(parent)
        rot=np.eye(3)
        if n.startswith(('finger2','finger3','finger4','finger5')):
            digit=int(n[6]);segment=int(n[8]);normal=-unit(np.cross(head('finger2-1.L')-head('finger5-1.L'),head('finger3-1.L')-head('wrist.L')))
            def frame(bone):
                y=unit(tail(bone)-head(bone));x=unit(np.cross(normal,y));return np.column_stack([x,y,np.cross(x,y)])
            bind=frame(n)
            if segment==1:
                y=unit(head('finger3-1.L')-head('wrist.L'));x=unit(np.cross(normal,y))
                desired=np.column_stack([x,y,np.cross(x,y)])@R.from_euler('x',-85,degrees=True).as_matrix()
            else:desired=pm[:3,:3]@frame(parent)@R.from_euler('x',-105 if segment==2 else -55,degrees=True).as_matrix()
            rot=desired@bind.T
        m=np.eye(4);m[:3,:3]=rot;m[:3,3]=pm[:3,:3]@head(n)+pm[:3,3]-rot@head(n)
    cache[n]=m;return m
def qm(a,b):return np.r_[a[3]*b[:3]+b[3]*a[:3]+np.cross(a[:3],b[:3]),a[3]*b[3]-a[:3]@b[:3]]
qs=[];ds=[]
# Solve the thumb against the outside of the closed index/middle fingers.
from scipy.optimize import least_squares
pn=-unit(np.cross(head('finger2-1.L')-head('finger5-1.L'),head('finger3-1.L')-head('wrist.L')))
def point(m,p):return m[:3,:3]@p+m[:3,3]
first=point(source_matrix('finger2-2.L'),(head('finger2-2.L')+tail('finger2-2.L'))*.5)
second=point(source_matrix('finger3-2.L'),(head('finger3-2.L')+tail('finger3-2.L'))*.5)
thumb_goal=first*.15+second*.85+pn*.18
thumb_ip_goal=first+pn*.18
thumb_names=[f'finger1-{i}.L' for i in (1,2,3)]
thumb_frames=[]
for n in thumb_names:
    y=unit(tail(n)-head(n));x=unit(np.cross(pn,y));thumb_frames.append(np.column_stack([x,y,np.cross(x,y)]))
def thumb_matrices(a):
    result=[];parent=np.eye(4)
    for i,n in enumerate(thumb_names):
        bind=thumb_frames[i]
        if i==0:world=bind@R.from_euler('xyz',a[:3],degrees=True).as_matrix()
        else:world=parent[:3,:3]@bind@R.from_euler('x',a[i+2],degrees=True).as_matrix()
        m=np.eye(4);m[:3,:3]=world@bind.T;m[:3,3]=point(parent,head(n))-m[:3,:3]@head(n)
        result.append(m);parent=m
    return result
def thumb_error(a):
    m=thumb_matrices(a);end=point(m[-1],tail(thumb_names[-1]));axis=unit(end-point(m[-1],head(thumb_names[-1])))
    ip=point(m[-1],head(thumb_names[-1]))
    return np.r_[(end-thumb_goal)*4,(ip-thumb_ip_goal)*2,(axis-unit(second-first))*.1,(a-np.array([-20,20,-20,-45,-45]))*.0002]
solution=least_squares(thumb_error,[-20,20,-20,-35,-30],bounds=([-70,-80,-80,-70,-55],[70,80,80,10,10]),max_nfev=140)
for n,m in zip(thumb_names,thumb_matrices(solution.x)):cache[n]=m
for n in names:
    m=source_matrix(n);q=R.from_matrix(m[:3,:3]).as_quat();qs.append(q);ds.append(.5*qm(np.r_[m[:3,3],0],q))
qs=np.array(qs);ds=np.array(ds);signed=w*np.where(qs[w.argmax(1)]@qs.T<0,-1,1)
qr=signed@qs;qd=signed@ds;norm=np.linalg.norm(qr,axis=1)[:,None];qr/=norm;qd/=norm;qd-=qr*(qr*qd).sum(1)[:,None]
cross=2*np.cross(qr[:,:3],points)
posed=points+qr[:,3:]*cross+np.cross(qr[:,:3],cross)+2*(-qd[:,3:]*qr[:,:3]+qr[:,3:]*qd[:,:3]+np.cross(qr[:,:3],qd[:,:3]))

archive=zipfile.ZipFile(args.jar)
def asset(name):return json.loads(archive.read('assets/projectseele/'+name))
geo=asset('geo/eva_unit01.geo.json');hands=asset('mesh/eva_unit01_anatomical_hands_r45.mesh.json')
contract=asset('hand_rigs/unit01/hand_rig_contract.json');spec={b['name']:b for b in geo['minecraft:geometry'][0]['bones']}
flip=np.array([-1.,1,1])
src_wrist=head('wrist.L');sy=unit(head('finger3-1.L')-src_wrist);sx=head('finger2-1.L')-head('finger5-1.L');sx=unit(sx-sy*(sx@sy));S=np.column_stack([sx,sy,np.cross(sx,sy)])
for side in ('l','r'):
    name='hand_'+side;h=contract['hands'][side];wrist=np.array(spec[name]['pivot'])*flip/16
    old_index=np.array(h['digits']['index']['joints'][0]['head_bind']);old_middle=np.array(h['digits']['middle']['joints'][0]['head_bind'])
    ty=unit((old_index+old_middle)/2-wrist);normal=np.array(h['palmar_normal_bind']);normal=unit(normal-ty*(normal@ty));tx=unit(np.cross(ty,-normal));T=np.column_stack([tx,ty,np.cross(tx,ty)])
    if side=='r':T[:,0]*=-1
    # Keep the original overall hand length, using the source palm/finger ratio.
    old_tip=np.array(h['digits']['middle']['joints'][-1]['tip_bind']);scale=np.linalg.norm(old_tip-wrist)/np.linalg.norm(tail('finger3-3.L')-src_wrist)
    # The imported EVA fingers had been stretched around a short palm. Keep
    # width, restore a compact closed-hand length instead of carrying that
    # old stretched silhouette into the authored corrective.
    A=T@np.diag([1,.78,1])@S.T*scale
    target=(posed-src_wrist)@A.T+wrist
    strike_source=np.mean([point(source_matrix(n),head(n)) for n in ('finger2-1.L','finger3-1.L')],axis=0)
    strike=(strike_source-src_wrist)@A.T
    correction=R.align_vectors(ty[None,:],unit(strike)[None,:])[0].as_matrix()
    # Orient the complete palm and all five fingers around the wrist. A local
    # sleeve bend cannot fix a hand that points away from the palm-side frame.
    target=(target-wrist)@correction.T+wrist
    ids=tri if np.linalg.det(A)>0 else tri[:,[0,2,1]]
    target=target[ids.reshape(-1)]
    raw=np.array(hands['parts'][name]['vertices']).reshape(-1,8)
    assert len(target)==38448 and len(raw)==40656
    old_rest=(raw[:,:3]+spec[name]['pivot'])*flip/16
    from scipy.spatial import cKDTree
    dorsal_normal=normal@correction.T
    tangent_x=tx@correction.T;tangent_y=ty@correction.T
    skin_vertex_count=len(target)
    # A closed shell keeps the two submitted dorsal surfaces apart. Its wrist
    # edge reaches the skin; no finger or palm vertices are removed or moved.
    def armour_patch(skin,centre,xaxis,yaxis,naxis,length):
        local=skin-centre
        surface=np.c_[local@xaxis,local@yaxis,local@naxis].reshape(-1,3,3)
        a,b,c=surface[:,0],surface[:,1],surface[:,2]
        e=b-a;f=c-a;det=e[:,0]*f[:,1]-e[:,1]*f[:,0]
        valid=np.abs(det)>1e-12
        def surface_depth(at):
                d=at-a[:,:2]
                s=np.divide(d[:,0]*f[:,1]-d[:,1]*f[:,0],det,out=np.zeros(len(det)),where=valid)
                t=np.divide(e[:,0]*d[:,1]-e[:,1]*d[:,0],det,out=np.zeros(len(det)),where=valid)
                hit=valid&(s>=-1e-7)&(t>=-1e-7)&(s+t<=1+1e-7)
                return float(np.min((a[:,2]+s*e[:,2]+t*f[:,2])[hit])) if np.any(hit) else None
        uv=[];depth=[];inner_clearance=[]
        for j in range(17):
            t=j/16;half=.105+.065*np.sin(np.pi*t/2)
            for attempt in range(17):
                row=[]
                for i in range(24):
                    u=2*i/23-1;corner=max(0,(abs(u)-.82)/.18)
                    # Continuous end taper, rather than reversing the corner
                    # offset abruptly between the two middle rows.
                    row.append([u*half,.065+length*.88*t+corner*.015*(1-2*t)])
                heights=[surface_depth(np.asarray(at)) for at in row]
                if all(h is not None for h in heights):break
                # Shrink the complete row, so adjacent edge vertices cannot
                # cross when the source dorsal silhouette becomes narrower.
                half*=.92
            else:raise ValueError('Dorsal plate has no underlying source surface')
            uv.extend(row);depth.extend(heights)
            root=min(1,t*8);inner_clearance.extend([.012*root*root*(3-2*root)]*24)
        uv=np.asarray(uv);depth=np.asarray(depth)
        plane=centre+uv[:,0,None]*xaxis+uv[:,1,None]*yaxis
        outer=plane+(depth-.020)[:,None]*naxis
        inner=plane+(depth-np.asarray(inner_clearance))[:,None]*naxis
        grid=np.vstack([outer,inner]);count=len(outer)
        ids=[]
        for j in range(16):
            for i in range(23):
                a=j*24+i;b=a+1;c=a+24;d=c+1
                ids.extend([a,c,b,b,c,d])
        outer_ids=np.asarray(ids).reshape(-1,3)
        first=outer[outer_ids[0]]
        if np.dot(np.cross(first[1]-first[0],first[2]-first[0]),-naxis)<0:outer_ids=outer_ids[:,[0,2,1]]
        triangles=[*outer_ids,*((outer_ids[:,[0,2,1]])+count)]
        chart=(uv-uv.min(0))/(uv.max(0)-uv.min(0))
        charts=[*chart[outer_ids],*chart[outer_ids[:,[0,2,1]]]]
        edges=Counter(tuple(sorted((int(a),int(b)))) for face in outer_ids for a,b in zip(face,np.roll(face,-1)))
        for face in outer_ids:
            for a,b in zip(face,np.roll(face,-1)):
                if edges[tuple(sorted((int(a),int(b))))]==1:
                    triangles.extend([[b,a,a+count],[b,a+count,b+count]])
                    # Each rim segment is an unfolded rectangle. Sharing the
                    # face's UV at both depths would collapse its tangent.
                    charts.extend([[[1,0],[0,0],[0,1]],[[1,0],[0,1],[1,1]]])
        triangles=np.asarray(triangles);result=grid[triangles].reshape(-1,3)
        directed=Counter((int(a),int(b)) for face in triangles for a,b in zip(face,np.roll(face,-1)))
        if any(n!=1 or directed[(b,a)]!=1 for (a,b),n in directed.items()):raise ValueError('Dorsal shell is not consistently closed')
        faces=outer[outer_ids];normals=np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0])
        if np.any(normals@(-naxis)<=1e-12):raise ValueError('Dorsal shell contains a folded outer face')
        faces=result.reshape(-1,3,3)
        if np.any(np.linalg.norm(np.cross(faces[:,1]-faces[:,0],faces[:,2]-faces[:,0]),axis=1)<=1e-12):raise ValueError('Dorsal shell contains a degenerate face')
        print(side,'closed dorsal shell',len(result),'vertices; no open edges or folded outer faces')
        return result,np.asarray(charts).reshape(-1,2)
    plate_rest,plate_uv=armour_patch(old_rest[:38448],wrist,tx,ty,normal,np.linalg.norm((old_index+old_middle)/2-wrist)*.83)
    plate,_=armour_patch(target,wrist,tangent_x,tangent_y,dorsal_normal,np.linalg.norm(strike)*.83)
    target=np.vstack([target,plate])
    # Close the cuff with a sleeve reaching inside the existing forearm shell.
    # Its far rim is forearm-owned and the hand rim follows the original skin.
    old_at={int(index):old_rest[k] for k,index in enumerate(ids.reshape(-1))}
    new_at={int(index):target[k] for k,index in enumerate(ids.reshape(-1))}
    elbow=np.array([-23.489652 if side=='l'else 23.489652,123.435069,7.737214])/16
    axis=unit(wrist-elbow);far_centre=wrist-axis*.14
    edge_ids=sorted({i for edge in boundary for i in edge})
    rim_centre=np.array([old_at[i]for i in edge_ids]).mean(0)
    def far_rim(p):
        r=p-rim_centre;r-=axis*(r@axis)
        return far_centre+unit(r)*.13
    bridge_old=[];bridge_target=[];bridge_weights=[]
    for a,b in boundary:
        # Winding follows the open source edge, closing toward the forearm.
        for vert,is_far in [(b,False),(a,False),(a,True),(b,False),(a,True),(b,True)]:
            rest=far_rim(old_at[vert])if is_far else old_at[vert]
            dest=rest.copy()if is_far else new_at[vert]
            bridge_old.append(rest);bridge_target.append(dest);bridge_weights.append(1 if is_far else 0)
    target=np.vstack([target,bridge_target])
    np.savez(base/f'natural_fist_{side}.npz',target=target,bridge_rest=np.array(bridge_old),bridge_forearm_weights=np.array(bridge_weights),plate_rest=plate_rest,
             skin_vertex_count=skin_vertex_count,plate_vertex_count=len(plate_rest),cuff_vertex_count=len(bridge_old),plate_uv=plate_uv)
    print(side,'source-based fist authored',len(target),'vertices')
