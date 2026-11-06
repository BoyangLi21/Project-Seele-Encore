"""Selected-input rig maths for R52 authoring; no import-time legacy paths."""
from pathlib import Path
import copy
import json
import numpy as np
from threadpoolctl import threadpool_limits
from scipy.spatial.transform import Rotation as R, Slerp
_r52_blas_threads=threadpool_limits(limits=1)

UNIT = 5 / 16
MIRROR = np.array([-1., 1., -1.])

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def multiply(a,b):
    a=np.asarray(a);b=np.asarray(b)
    return np.concatenate((a[...,:3]*b[...,3:]+b[...,:3]*a[...,3:]+np.cross(a[...,:3],b[...,:3]),a[...,3:]*b[...,3:]-np.sum(a[...,:3]*b[...,:3],axis=-1,keepdims=True)),axis=-1)

def skin(rest, matrices, ids, weights):
    q=R.from_matrix(matrices[:,:3,:3]).as_quat()
    d=.5*multiply(np.c_[matrices[:,:3,3],np.zeros(len(q))],q)
    qs=q[ids];ds=d[ids]
    sign=np.where(np.sum(qs*qs[:,0:1,:],axis=-1,keepdims=True)<0,-1,1)
    q=np.sum(qs*weights[:,:,None]*sign,axis=1)
    d=np.sum(ds*weights[:,:,None]*sign,axis=1)
    norm=np.linalg.norm(q,axis=1,keepdims=True);q/=norm;d/=norm;d-=q*np.sum(q*d,axis=1,keepdims=True)
    return R.from_quat(q).apply(rest)+2*multiply(d,q*[-1,-1,-1,1])[:,:3]

class Rig:
    def __init__(self,bones,mesh,angel=False):
        self.rig={b['name']:b for b in bones};self.names=list(self.rig)
        self.P={n:np.asarray(b['pivot'],float)*[-1,1,1] for n,b in self.rig.items()}
        self.parents={n:b.get('parent') for n,b in self.rig.items()}
        self.mesh=mesh;self.angel=angel;self.parts={};self.uv={}
        self.hand_contract=None;self.hand_mesh=None
        for n,p in mesh['parts'].items():
            raw=np.asarray(p['vertices']).reshape(-1,8)
            self.parts[n]=(raw[:,:3]+(np.zeros(3) if angel else p['pivot']))*[-1,1,1]
            self.uv[n]=raw[:,3:5]
        if angel:
            v=self.parts['root'];_,ix,self.inverse=np.unique(np.round(v,6),axis=0,return_index=True,return_inverse=True)
            self.vertices=v[ix];self.ids=np.asarray(mesh['skin']['indices']).reshape(-1,4)[ix]
            self.weights=np.asarray(mesh['skin']['weights']).reshape(-1,4)[ix]
        self.knees={s:self.P['shin_'+s].copy() for s in ('l','r')}
        self.elbows={s:self.P['forearm_'+s].copy() for s in ('l','r')}
        if not angel:
            for s in ('l','r'):
                self.knees[s]+=np.array([0,11.4,0])
                self.elbows[s]=np.array([(-1 if s=='l' else 1)*23.489652,123.435069,7.737214])
        self.feet={}
        for s in ('l','r'):
            if angel:
                weight=np.where(self.ids==self.names.index('foot_'+s),self.weights,0).sum(1)
                self.feet[s]=self.vertices[weight>.6]-self.P['foot_'+s]
            else:self.feet[s]=self.parts['foot_'+s]-self.P['foot_'+s]
        self.height=self.P['head'][1]

    def pose(self):return Pose(self)
    def decode(self,f,names):
        p=self.pose()
        for n,(w,x,y,z) in zip(names,f['rotation_wxyz']):
            if n in p.q:p.q[n]=R.from_quat([-x,-y,z,w])
        for n,v in f.get('bone_position_xyz',{}).items():
            if n in p.p:p.p[n]=np.asarray(v)*[-1,1,1]
        p.p['root']=np.asarray(f['root_m'])*112*[-1,1,1]
        return p

class Pose:
    def __init__(self,rig):
        self.rig=rig;self.q={n:R.identity() for n in rig.names};self.p={n:np.zeros(3) for n in rig.names};self.cache={}
    def __deepcopy__(self,memo):
        p=Pose(self.rig);p.q=dict(self.q);p.p={n:v.copy() for n,v in self.p.items()};return p
    def setq(self,n,q):self.q[n]=q;self.cache.clear()
    def setp(self,n,p):self.p[n]=np.asarray(p,float);self.cache.clear()
    def matrix(self,n):
        if n in self.cache:return self.cache[n]
        pivot=self.rig.P[n];rotation=self.q[n].as_matrix();m=np.eye(4);m[:3,:3]=rotation
        m[:3,3]=self.p[n]+pivot-rotation@pivot
        parent=self.rig.parents[n];self.cache[n]=(self.matrix(parent) if parent else np.eye(4))@m
        return self.cache[n]
    def parent(self,n):return self.matrix(self.rig.parents[n]) if self.rig.parents[n] else np.eye(4)
    def point(self,n,p=None):return (self.matrix(n)@np.r_[self.rig.P[n] if p is None else p,1])[:3]
    def encode(self,names,contacts=(True,True)):
        qs=[]
        for n in names:
            x,y,z,w=self.q.get(n,R.identity()).as_quat();qs.append([w,-x,-y,z])
        return dict(root_m=np.round(self.p['root']*[-1,1,1]/112,8).tolist(),rotation_wxyz=np.round(qs,8).tolist(),foot_contact=list(contacts),bone_position_xyz={n:np.round(v*[-1,1,1],7).tolist() for n,v in self.p.items() if n!='root' and np.linalg.norm(v)>1e-7})
    def surface(self,parts=None):
        if self.rig.angel:
            matrices=np.asarray([self.matrix(n) for n in self.rig.names])
            return skin(self.rig.vertices,matrices,self.rig.ids,self.rig.weights)[self.rig.inverse]
        chosen=parts or [n for n in self.rig.parts if n in self.q]
        verts=[]
        for n in chosen:
            rest=self.rig.parts[n];k=self.rig.mesh.get('jointSkins',{}).get(n)
            if self.rig.hand_mesh is not None and n in ('hand_l','hand_r'):
                k=self.rig.hand_mesh['jointSkins'][n];names=list(k['influences'])
                weights=np.column_stack([k['influences'][name] for name in names]);matrices=[]
                for name in names:
                    inverse=np.asarray(k['inverseBindColumnMajor'][name]).reshape(4,4).T.copy();inverse[:3,3]*=16
                    matrices.append(self.matrix(name)@inverse)
                matrices=np.asarray(matrices);q=R.from_matrix(matrices[:,:3,:3]).as_quat();d=.5*multiply(np.c_[matrices[:,:3,3],np.zeros(len(names))],q)
                ref=np.argmax(weights,axis=1);sign=np.where((q[None,:,:]*q[ref,None,:]).sum(2)<0,-1,1);w=weights*sign
                real=w@q;dual=w@d;norm=np.linalg.norm(real,axis=1,keepdims=True);real/=norm;dual/=norm;dual-=real*(real*dual).sum(1,keepdims=True)
                v=R.from_quat(real).apply(rest)+2*multiply(dual,real*[-1,-1,-1,1])[:,:3]
            elif k and 'influences' in k:
                names=list(k['influences']);weights=np.column_stack([k['influences'][name] for name in names]);matrices=np.asarray([self.matrix(name) for name in names])
                q=R.from_matrix(matrices[:,:3,:3]).as_quat();d=.5*multiply(np.c_[matrices[:,:3,3],np.zeros(len(names))],q)
                reference=np.argmax(weights,axis=1);sign=np.where((q[None,:,:]*q[reference,None,:]).sum(2)<0,-1,1);w=weights*sign
                real=w@q;dual=w@d;norm=np.linalg.norm(real,axis=1,keepdims=True);real/=norm;dual/=norm;dual-=real*(real*dual).sum(1,keepdims=True)
                v=R.from_quat(real).apply(rest)+2*multiply(dual,real*[-1,-1,-1,1])[:,:3]
            elif k and k['otherBone'] in self.q:
                ids=np.tile([0,1,0,0],(len(rest),1));w=np.asarray(k['weights']);weights=np.c_[1-w,w,np.zeros((len(w),2))]
                v=skin(rest,np.asarray([self.matrix(n),self.matrix(k['otherBone'])]),ids,weights)
            else:v=(np.c_[rest,np.ones(len(rest))]@self.matrix(n).T)[:,:3]
            verts.append(v)
        return np.vstack(verts)
    def ground(self):self.setp('root',self.p['root']+[0,-self.surface()[:,1].min(),0])

def selected(body_path,assets,angel_rig):
    body=read(body_path);assets=Path(assets);doc=read(angel_rig)
    bones=copy.deepcopy(body['rigs']['1']);known={b['name'] for b in bones}
    bones.extend(b for b in read(assets/'geo/eva_unit01.geo.json')['minecraft:geometry'][0]['bones'] if b['name'] not in known)
    hand_contract=read(assets/'hand_rigs/unit01/hand_rig_contract.json');known={b['name'] for b in bones}
    bones.extend(b for b in hand_contract['new_bones'] if b['name'] not in known)
    hero=Rig(bones,read(assets/'mesh/eva_unit01.mesh.json'))
    hero.hand_contract=hand_contract;hero.hand_mesh=read(assets/'mesh/eva_unit01_anatomical_hands_r45.mesh.json')
    for n in list(hero.parts):
        if n.startswith('finger_'):del hero.parts[n];del hero.uv[n]
    for n,part in hero.hand_mesh['parts'].items():
        raw=np.asarray(part['vertices']).reshape(-1,8);hero.parts[n]=(raw[:,:3]+part['pivot'])*[-1,1,1];hero.uv[n]=raw[:,3:5]
    alien=Rig(doc['bones'],read(assets/'mesh/sachiel.mesh.json'),True)
    alien.core=(np.array([0,12.63,1.42])-[0,doc['source_floor'],0])*doc['source_scale']*[-1,1,-1]
    alien.eye=(np.array([0,15.05,1.40])-[0,doc['source_floor'],0])*doc['source_scale']*[-1,1,-1]
    alien.waist=(np.array([0,8.405552,.129547])-[0,doc['source_floor'],0])*doc['source_scale']*[-1,1,-1]
    return body,hero,alien

def hand_controls(p,left='relaxed',right='relaxed'):
    contract=p.rig.hand_contract
    if contract is None:return
    for side,choice_name in [('l',left),('r',right)]:
        choice=contract['pose_controls'][choice_name];sign=1 if side=='l' else -1
        for digit,data in contract['hands'][side]['digits'].items():
            for j in data['joints']:
                name=j['name'];index=j['index']
                if name in choice.get('bone_angles',{}):angles=np.asarray(choice['bone_angles'][name],float)
                elif digit=='thumb':angles=np.asarray(choice['thumb'][index],float)
                else:angles=np.array([choice.get(digit,choice['fingers'])[index],0,choice.get('splay',{}).get(digit,0) if index==0 else 0],float)
                limits=np.asarray(j['anatomical_limits_degrees']);angles=np.clip(angles,limits[:,0],limits[:,1])
                neutral=R.from_quat(j['neutral_local_quaternion_xyzw']);local=R.from_euler('ZYX',[sign*angles[2],sign*angles[1],-angles[0]],degrees=True)
                p.setq(name,neutral*local);p.setp(name,[0,0,0])

def hand_carry(p,sides=('l','r')):
    contract=p.rig.hand_contract
    if contract is None:return
    for side in sides:
        frame=contract['hands'][side];hand='hand_'+side
        along=p.point(hand)-p.point('forearm_'+side,p.rig.elbows[side]);along/=np.linalg.norm(along)
        inward=p.matrix('torso_upper')[:3,:3]@np.array([1 if side=='l' else -1,0.,0.]);inward-=along*(inward@along);inward/=np.linalg.norm(inward)
        source_along=np.asarray(frame['longitudinal_bind']);source_along/=np.linalg.norm(source_along)
        source_normal=np.asarray(frame['palmar_normal_bind']);source_normal-=source_along*(source_normal@source_along);source_normal/=np.linalg.norm(source_normal)
        source=np.column_stack([source_normal,source_along,np.cross(source_normal,source_along)]);target=np.column_stack([inward,along,np.cross(inward,along)])
        p.setq(hand,R.from_matrix(p.parent(hand)[:3,:3]).inv()*R.from_matrix(target@source.T))

def ease(t):
    t=float(np.clip(t,0,1));return t*t*t*(10+t*(-15+6*t))

def mix(a,b,t):
    t=float(np.clip(t,0,1));p=copy.deepcopy(a);names=list(a.q)
    qa=np.asarray([a.q[n].as_quat() for n in names]);qb=np.asarray([b.q[n].as_quat() for n in names])
    dot=(qa*qb).sum(1);qb=np.where((dot<0)[:,None],-qb,qb);dot=np.clip(np.abs(dot),0,1)
    angle=np.arccos(dot);sine=np.sin(angle);safe=np.maximum(sine,1e-8)
    left=np.where(dot>.9995,1-t,np.sin((1-t)*angle)/safe);right=np.where(dot>.9995,t,np.sin(t*angle)/safe)
    quaternions=qa*left[:,None]+qb*right[:,None];rotations=R.from_quat(quaternions)
    for j,n in enumerate(names):p.q[n]=rotations[j];p.p[n]=a.p[n]*(1-t)+b.p[n]*t
    p.cache={};return p
