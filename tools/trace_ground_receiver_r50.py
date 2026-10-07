"""One read-only trace of the real power-locked Unit02 receiving trajectory.

Checks real saved block shapes, not another game launch or a substitute entity.
Dynamic occupants and native client interpolation still require the actual run.
"""
from pathlib import Path
import json,itertools,math
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
from measure_world_r40 import MeasuredWorld

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r50/native_client/ejection_preflight'
WORLD=ROOT/'artifacts/rebuild_r49/native_qa/worlds/SEELE_R49_QA'

def main():
    saved=json.loads((OUT/'ground_receiver_source.json').read_text())
    profile=json.loads((ROOT/'artifacts/rebuild_r49/runtime/projectseele-local-maps/eva_body_r44.json').read_text())
    rig={b['name']:b for b in profile['rigs']['2']}
    piv={n:np.array(b['pivot'])*[-1,1,1]/16 for n,b in rig.items()}
    support={n:np.asarray(v)/16 for n,v in profile['support'].items()}
    frozen=saved['R30FrozenPose'];pos=np.array(saved['Pos']);yaw=saved['Rotation'][0]
    world_rotation=R.from_euler('y',180-yaw,degrees=True).as_matrix()
    lerps={};positions={}
    for n,b in rig.items():
        values=frozen.get(n,[0,0,0,0,0,0,1,1,1])
        start=R.from_euler('xyz',values[:3]);bind=np.array(b.get('rotation',b.get('bindRotationDegrees',[0,0,0])))*[-1,-1,1]
        target=R.from_euler('xyz',bind,degrees=True)
        if n=='root':target=R.from_euler('y',yaw-180,degrees=True)*target
        lerps[n]=Slerp([0,1],R.from_quat([start.as_quat(),target.as_quat()]))
        positions[n]=np.array(values[3:6])*[-1,1,1]/16
    corners=np.array(list(itertools.product([0,1],repeat=3)))
    def pose(age):
        def smooth(t):
            t=max(0,min(1,t));return t*t*t*(t*(t*6-15)+10)
        t=smooth((age-80)/240)
        rot={n:f(t).as_matrix()for n,f in lerps.items()};trans={n:p*(1-t)for n,p in positions.items()}
        if t>0:
            for side in ['l','r']:
                for fam in ['shin_','forearm_']:
                    n=fam+side;mark=('r30_knee_socket_'if fam=='shin_'else'r30_elbow_socket_')+side
                    centre=piv.get(mark,piv[n]+[0,11.4/16,0]if fam=='shin_'else np.array([-23.489652 if side=='l' else 23.489652,123.435069,7.737214])/16)
                    delta=centre-piv[n];trans[n]=delta-rot[n]@delta
        mats={}
        def matrix(n):
            if n not in mats:
                m=np.eye(4);m[:3,:3]=rot[n];m[:3,3]=trans[n]+piv[n]-rot[n]@piv[n]
                parent=rig[n].get('parent');mats[n]=matrix(parent)@m if parent else m
            return mats[n]
        def points(n,vertices):
            m=matrix(n);return (vertices@m[:3,:3].T+m[:3,3])*5
        parts={n:points(n,v)for n,v in support.items()if n in rig}
        low=min(p[:,1].min()for p in parts.values())
        lift=(max(0,-low)if t>0 else 0)+2*smooth((age-40)/40)*smooth((360-age)/40)
        boxes=[]
        def box(n,p,padding):
            mn=p.min(axis=0)-padding;mx=p.max(axis=0)+padding
            pts=(mn+corners*(mx-mn)+[0,lift,0])@world_rotation.T+pos
            boxes.append((n,pts.min(axis=0),pts.max(axis=0)))
        for n,vertices in parts.items():box(n,vertices,.08)
        for side in ['l','r']:
            for a,b in [('arm_','forearm_'),('forearm_','wrist_'),('wrist_','finger_middle_')]:
                a+=side;b+=side
                if a in rig and b in rig:box(a+'->'+b,np.vstack([points(a,piv[a][None,:]),points(b,piv[b][None,:])]),3)
        return boxes
    frames=[pose(i)for i in range(361)]
    low=np.floor(np.min([v[1]for f in frames for v in f],axis=0)-1).astype(int)
    high=np.ceil(np.max([v[2]for f in frames for v in f],axis=0)+1).astype(int)
    measured=MeasuredWorld(WORLD);measured.box(low,high);measured.load()
    shapes=json.loads((WORLD/'native_collision_shapes.json').read_text(encoding='utf-8-sig'))
    obstacles=[];unknown=[]
    for x in range(low[0],high[0]+1):
        for y in range(low[1],high[1]+1):
            for z in range(low[2],high[2]+1):
                state=measured.get(x,y,z)
                if state in {'minecraft:air','minecraft:cave_air','minecraft:void_air'}:continue
                if state not in shapes:unknown.append([x,y,z,state]);continue
                for sh in shapes[state]:obstacles.append(([x,y,z],state,np.array(sh[:3])+[x,y,z],np.array(sh[3:])+[x,y,z]))
    lo=np.array([o[2]for o in obstacles]);hi=np.array([o[3]for o in obstacles])
    failures=[]
    for age in range(1,361):
        for before,after in zip(frames[age-1],frames[age]):
            name,a,A=before;_,b,B=after
            old=np.maximum(0,np.minimum(A,hi)-np.maximum(a,lo)).prod(axis=1)
            sweep=np.maximum(0,np.minimum(np.maximum(A,B)-.001,hi)-np.maximum(np.minimum(a,b)+.001,lo)).prod(axis=1)
            for index in np.nonzero(sweep>old+.001)[0]:
                xyz,state,_,_=obstacles[index]
                if xyz[1]==-411 and b[1]>=-410.081 and state=='projectseele:nerv_floor_panel':continue
                failures.append(dict(tick=age,part=name,block=xyz,state=state,previous=float(old[index]),next=float(sweep[index])));break
            if failures:break
        if failures:break
    report=dict(source='ground_receiver_source.json',original_uuid='b55591fa-dcfa-4e6f-9591-2b1eab7cb92e',steps=360,
                whole_load_bounds=[low.tolist(),high.tolist()],unknown=unknown[:20],unknown_count=len(unknown),first_failure=failures,
                final_feet={n:[a.tolist(),b.tolist()]for n,a,b in frames[-1]if n.startswith('foot_')},
                scope='Read-only actual frozen pose, nine support hulls and available arm chains, block collision shapes. Dynamic entities/native renderer not simulated.',world_written=False)
    (OUT/'ground_receiver_solid_trace.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
