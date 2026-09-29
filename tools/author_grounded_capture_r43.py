"""Candidate complete grounded performance from calibrated capture.

The original capture owns pelvis/chest/limb orientation; the anatomy adapter
preserves that frame. Contacts own the feet, not the thigh's twist. Files stay
in the review directory until actual gameplay and transition review passes.
"""
from pathlib import Path
import argparse,copy,hashlib,json,shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_combat_performance_r36 as performance
from author_combat_r35 import Actor
from audit_retarget_basis_r43 import AnatomicalRetarget
from rebuild_stance_hinges_r41 import reconstruct,reachable_root,swing
from author_articulation_r42 import hands

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/repair_r43/grounded_capture'

def anatomy(actor,p,closure=1,poles=None):
    for side in ('l','r'):
        foot='foot_'+side;goal=p.point(foot).copy();orientation=R.from_matrix(p.matrix(foot)[:3,:3])
        reconstruct(actor,p,side,goal,orientation,p.q['leg_'+side])
        # Preserve THIS recorded shoulder frame. Carrying the previous frame's
        # shoulder instead discards the captured elbow plane during a pull.
        upper,lower,end='arm_'+side,'forearm_'+side,'hand_'+side;joint=actor.elbows[side]
        target=p.point(end).copy();orientation=R.from_matrix(p.matrix(end)[:3,:3]);u=joint-actor.P[upper];v=actor.P[end]-joint;axis=np.array([1.,0,0])
        a=u@(v-axis*(axis@v));b=u@np.cross(axis,v);c=(u@axis)*(v@axis);amplitude=np.hypot(a,b);neutral=np.arctan2(b,a)
        la=np.linalg.norm(u);lb=np.linalg.norm(v);delta=target-p.point(upper)
        maximum=np.sqrt(la*la+lb*lb+2*(amplitude+c))*.9999
        minimum=np.sqrt(max(0,la*la+lb*lb+2*(a*np.cos(2.85)+b*np.sin(2.85)+c)))+.0001
        length=np.clip(np.linalg.norm(delta),minimum,maximum);angle=neutral+np.arccos(np.clip(((length*length-la*la-lb*lb)/2-c)/max(amplitude,1e-8),-1,1))
        hinge=R.from_rotvec(axis*angle);authored=R.from_matrix(p.matrix(upper)[:3,:3]);world=swing(authored.apply(u+hinge.apply(v)),delta)*authored
        p.setq(upper,R.from_matrix(p.parent(upper)[:3,:3]).inv()*world);p.setq(lower,hinge)
        offset=joint-actor.P[lower];p.setp(lower,offset-hinge.apply(offset));p.setq(end,R.from_matrix(p.parent(end)[:3,:3]).inv()*orientation)
    hands(actor,p,closure)
    return p

def plant(actor,pose,anchors,trajectory,reference):
    goals={};orientations={}
    for side in ('l','r'):
        original=R.from_matrix(pose.matrix('foot_'+side)[:3,:3])
        pitch=np.arcsin(np.clip(original.apply([0,0,-1])[1],-1,1))-reference[side]
        q=R.from_euler('y',10 if side=='l' else -10,degrees=True)*R.from_euler('x',np.clip(pitch,-.4,.4));orientations[side]=q
        point=anchors[side]-trajectory;point[1]=-q.apply(actor.feet[side])[:,1].min();goals[side]=point
    reachable_root(actor,pose,goals)
    for side in ('l','r'):reconstruct(actor,pose,side,goals[side],orientations[side],pose.q['leg_'+side])
    return pose

def main(rig):
    OUT.mkdir(exist_ok=True);source_dir=OUT/'source';source_dir.mkdir(exist_ok=True);performance.common.OUT=source_dir
    for key in range(5):
        sibling=OUT/f'eva_gameplay_r42_{key}.json'
        if key!=rig and not sibling.exists():shutil.copy2(ROOT/f'run/projectseele-local-maps/eva_gameplay_r42_{key}.json',sibling)
    actor=Actor(rig);file=ROOT/f'run/projectseele-local-maps/eva_gameplay_r42_{rig}.json';data=json.loads(file.read_text('utf8'));old=copy.deepcopy(data)
    guard_clip,meta=performance.captured(actor,'StanceBoxer',False,'guard',AnatomicalRetarget,anatomy)
    guard=performance.sample(actor,data,guard_clip,.5);reports=[]
    anchors={'l':np.array([-actor.width,0,-actor.height*.115]),'r':np.array([actor.width,0,actor.height*.115])}
    for label in ('guard','jab','cross','hook','heavy'):
        source='StanceBoxer' if label=='guard' else 'ArmsSinglePunch2' if label=='hook' else performance.common.SELECTION[label][0]
        clip,meta=performance.captured(actor,source,label in ('jab','hook'),label,AnatomicalRetarget,anatomy)
        old_clip=data['clips']['r32_'+label];count=len(old_clip['frames']);poses=[];travel=[]
        from scipy.interpolate import PchipInterpolator
        curve=PchipInterpolator([0,old_clip.get('contact_phase',.45),1],[0,clip['contact_phase'],1]) if label!='guard' else lambda t:t
        for t in np.linspace(0,1,count):
            phase=float(curve(t));p=performance.sample(actor,data,clip,phase)
            if label!='guard':
                p=performance.mix(copy.deepcopy(guard),p,performance.ease(t/.13)*(1-performance.ease((t-.83)/.17)))
            else:
                p=performance.mix(p,copy.deepcopy(guard),max(1-performance.ease(t/.15),performance.ease((t-.85)/.15)))
            at=phase*(len(clip['trajectory_m'])-1);a=int(at);f=at-a
            trajectory=np.asarray(clip['trajectory_m'][a])*(1-f)+np.asarray(clip['trajectory_m'][min(a+1,len(clip['trajectory_m'])-1)])*f
            poses.append(p);travel.append(trajectory.tolist())
        reference={s:np.arcsin(np.clip(R.from_matrix(poses[0].matrix('foot_'+s)[:3,:3]).apply([0,0,-1])[1],-1,1)) for s in ('l','r')}
        frames=[]
        for index,p in enumerate(poses):
            p=plant(actor,p,anchors,np.asarray(travel[index])*[-112,112,112],reference);hands(actor,p,.58 if label=='guard' else 1)
            frames.append(actor.rig.encode(p,(True,True),data['bones']))
        old_clip.update(frames=frames,trajectory_m=travel,step_contacts=[[True,True]]*len(frames),stance_locked=True,
            support='Captured anatomical limb frame with persistent sole contacts')
        reports.append(dict(clip=label,source=meta,frames=len(frames),timing_and_damage='Existing runtime parameters unchanged'))
    data['r43_grounded_capture']=dict(schema=1,input_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),clips=reports,
        status='CANDIDATE: no native quality acceptance yet',method='Calibrated source hinge axes -> complete captured pose -> fixed anatomical hinges preserving each source frame -> foot contact retarget; no whole-clip transported shoulder replacement')
    target=OUT/f'eva_gameplay_r42_{rig}.json';target.write_text(json.dumps(data,separators=(',',':')),'utf8')
    (OUT/f'provenance_{rig}.json').write_text(json.dumps(data['r43_grounded_capture'],indent=2),'utf8');print('Source-directed candidate rig',rig,'clips',len(reports),target,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--rig',type=int,default=1,choices=range(5));a=p.parse_args();main(a.rig)
