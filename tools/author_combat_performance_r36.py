"""Retain a captured whole-body performance instead of driving wrist splines.

The source supplies pelvis, chest, head, both limbs and the order of support.
Only rig anatomy, fist articulation, clip timing and entry/release are adapted.
No source images, character meshes or world data are rewritten by this tool.
"""
from pathlib import Path
import argparse,copy,json,hashlib
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.spatial.transform import Rotation as R,Slerp
import author_combat_r35 as author
import author_gameplay_motion_r32 as common
import anatomical_hinge_r35 as hinge
import combat_hand_pose_r36 as hands
from study_combat_performance_r36 import decode

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/combat_direction_r36'
OLD=ART/'profiles';OUT=ART/'performance_profiles';SOURCE=ROOT/'artifacts/combat_sortie_r32/gameplay_sources'

def ease(t):
    t=float(np.clip(t,0,1));return t*t*(3-2*t)

def mix(a,b,t):
    keys=list(a.q);qa=np.array([a.q[n].as_quat() for n in keys]);qb=np.array([b.q[n].as_quat() for n in keys]);dot=(qa*qb).sum(-1);qb*=np.where(dot<0,-1,1)[:,None];angle=np.arccos(np.clip(abs(dot),0,1));s=np.sin(angle)
    wa=np.divide(np.sin((1-t)*angle),s,out=np.full_like(s,1-t),where=s>1e-6);wb=np.divide(np.sin(t*angle),s,out=np.full_like(s,t),where=s>1e-6);qs=R.from_quat(qa*wa[:,None]+qb*wb[:,None])
    for i,n in enumerate(keys):
        a.setq(n,qs[i]);a.setp(n,a.p[n]*(1-t)+b.p[n]*t)
    return a

def sample(actor,data,clip,t):
    frames=clip['frames'];f=float(np.clip(t,0,1))*(len(frames)-1);a=int(f);b=min(a+1,len(frames)-1)
    return mix(decode(actor,data,frames[a]),decode(actor,data,frames[b]),f-a)

def anatomy(a,p,closure=1,poles=None):
    for side in ('l','r'):
        # Preserve the captured bend plane and end orientation. The solver
        # repairs the EVA hinge, rather than replacing the actor's limb path.
        for upper,lower,end,joint,axis in [('arm_','forearm_','hand_',a.elbows[side],[1,0,0]),('leg_','shin_','foot_',a.knees[side],[-1,0,0])]:
            names=[s+side for s in (upper,lower,end)];orientation=R.from_matrix(p.matrix(names[2])[:3,:3]);target=p.point(names[2]);middle=(p.matrix(names[0])@np.r_[joint,1])[:3]
            pole=R.from_matrix(p.matrix('root')[:3,:3]).apply([0,0,-1]) if lower=='shin_' else middle-p.point(names[0])
            if lower=='forearm_' and poles is not None:
                direction=hinge.unit(target-p.point(names[0]));pole=hinge.unit(pole-direction*(pole@direction))
                if side in poles:
                    old_direction,old_pole=poles[side];previous=author.base.rt.eva.arc(old_direction,direction).apply(old_pole)
                    previous=hinge.unit(previous-direction*(previous@direction));angle=np.arctan2(direction@np.cross(previous,pole),np.clip(previous@pole,-1,1))
                    pole=R.from_rotvec(direction*np.clip(angle,-.14,.14)).apply(previous)
                poles[side]=(direction.copy(),pole.copy())
            hinge.solve(p,a.P,*names,joint,target,pole,axis,orientation)
        if not a.angel:
            n='hand_'+side;finger=a.P['finger_middle_'+side]-a.P[n]
            # A closed fist follows the forearm's roll. The mocap's sparse
            # finger markers cannot provide a reliable independent wrist roll.
            p.setq(n,author.base.rt.eva.arc(finger,a.P[n]-a.elbows[side]))
    if not a.angel:hands.apply(p,a.rig.rig,closure)
    return p

def record(a,p,contacts):
    f=p.encode() if a.angel else a.rig.encode(p,tuple(contacts),hands.names(a.rig.rig));f['foot_contact']=list(contacts);return f

def captured(a,source,mirror,label,retarget_class=None,pose_adapter=None):
    adapter=pose_adapter or anatomy
    h,meta=common.human(source,mirror);retarget=(retarget_class or common.rt.Retarget)(h,a.angel,calibrated_trunk=True)
    poses=[];travel=[];poles={}
    # The old 'feet' retarget snapped an ankle to the floor at a Boolean
    # threshold. It could change knee flexion by 100 degrees in one frame.
    # Keep continuous measured limb directions first, then ground the soles.
    for f in np.linspace(1,h.frames-1,121):
        p,delta,_=retarget.pose(f,support='air');poses.append(adapter(a,p,poles=poles));travel.append(delta)
    palms={s:np.array([p.point('hand_'+s)-(p.point('leg_l')+p.point('leg_r'))*.5 for p in poses]) for s in ('l','r')}
    lead=max(palms,key=lambda s:np.ptp(palms[s][:,2]));contact=int(np.argmax(-palms[lead][:,2]))
    if source in ('SlapDownwards','AerialSlapDownwards'):
        lead=max(palms,key=lambda s:np.max(-np.gradient(palms[s][:,1])));contact=int(np.argmax(-np.gradient(palms[lead][:,1])))
    if label=='stomp':
        lead=max(('l','r'),key=lambda s:np.ptp([p.point('foot_'+s)[1] for p in poses]));heights=np.array([p.point('foot_'+lead)[1] for p in poses]);peak=heights.argmax();contact=peak+int(np.argmin(heights[peak:]))
    contact=int(np.clip(contact,10,108));aim=palms[lead][contact];turn=R.from_euler('y',0 if label in ('stomp','guard') else np.arctan2(aim[0],-aim[2]))
    world=turn.apply(np.array(travel)-travel[0]);world[:,1]=0
    frames=[]
    for p in poses:
        common.rotate_stage(p,a.rig,turn)
        floor={s:float((R.from_matrix(p.matrix('foot_'+s)[:3,:3]).apply(a.feet[s])+p.point('foot_'+s))[:,1].min()) for s in ('l','r')}
        low=min(floor.values());p.setp('root',p.p['root']+[0,-low,0]);frames.append(record(a,p,[floor[s]-low<.8 for s in ('l','r')]))
    c=dict(frames=frames,trajectory_m=(world*[-1,1,1]/112).tolist(),contact_phase=contact/120,leading_side=lead,duration_seconds=(h.frames-2)/h.fps,loop=label=='guard',support='captured_soles')
    return c,meta

def convert(a,data,c,label,guard=None):
    contact=.55 if label=='heavy' or label.startswith('low_') else .45
    src=float(c['contact_phase']);curve=PchipInterpolator([0,contact,1],[0,src,1])
    frames=[];travel=[];count=101;poles={}
    for t in np.linspace(0,1,count):
        phase=float(curve(t));p=sample(a,data,c,phase);at=round(phase*(len(c['frames'])-1));contacts=c['frames'][at]['foot_contact']
        if guard is not None:
            w=max(1-ease(t/.10),ease((t-.80)/.20));p=mix(p,copy.deepcopy(guard),w)
        p=anatomy(a,p,.72 if label.startswith('berserk') else 1,poles)
        frames.append(record(a,p,contacts))
        pos=np.array(c['trajectory_m']);f=phase*(len(pos)-1);i=int(f);travel.append(pos[i]*(1-(f-i))+pos[min(i+1,len(pos)-1)]*(f-i))
    durations={'jab':1.35,'cross':2.35,'hook':1.8,'heavy':2.4,'shove':1.6,'stomp':2.15} if a.angel else {'jab':1.15,'cross':1.25,'hook':1.35,'heavy':1.55,'shove':1.6,'stomp':2.15}
    out=copy.deepcopy(c);out.update(frames=frames,trajectory_m=np.array(travel).tolist(),contact_phase=contact,
            intent='whole_body_performance',release_phase=.90,source_contact_phase=src,
            source_duration_seconds=c['duration_seconds'],duration_seconds=durations.get(label,1.3),step_contacts=[f['foot_contact'] for f in frames])
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rigs',default='1,sachiel,0,2,3,4');args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    common.OUT=ART/'performance_sources';common.OUT.mkdir(exist_ok=True)
    for raw in args.rigs.split(','):
        key=raw if raw=='sachiel' else int(raw);a=author.Actor(key);file='sachiel_gameplay_r32.json' if a.angel else f'eva_gameplay_r32_{key}.json'
        original=json.loads((SOURCE/file).read_text());data=json.loads((OLD/file).read_text());new={}
        guard_clip,guard_meta=captured(a,'StanceBoxer',False,'guard');original['bones']=a.names if a.angel else hands.names(a.rig.rig)
        guard=anatomy(a,sample(a,original,guard_clip,.5))
        for label in ('jab','cross','hook','heavy','shove','stomp'):
            source=common.SELECTION[label][0]
            if label=='hook' and not a.angel:source='ArmsSinglePunch2'
            if label=='heavy' and a.angel:source='SlapDownwards'
            c,meta=captured(a,source,label in ('jab','hook'),label);original['sources'][label]=meta
            new['r32_'+label]=convert(a,original,c,label,guard)
            data['sources'][label]=dict(original['sources'][label],adaptation='Whole-body capture with rig-specific anatomical hinges and complete fist channels')
        # Source breathing stance, with exact loop closure; no independent arm
        # sway competes with the recorded shoulder girdle.
        g=copy.deepcopy(guard_clip);g['frames']=[]
        for t in np.linspace(0,1,81):
            p=anatomy(a,sample(a,original,guard_clip,t));p=mix(p,copy.deepcopy(guard),max(1-ease(t/.15),ease((t-.85)/.15)))
            g['frames'].append(record(a,p,[True,True]))
        g.update(trajectory_m=[[0,0,0]]*81,intent='captured_guard',duration_seconds=3.0);new['r32_guard']=g
        # Low-target and feral strikes retain the captured torso-led downward
        # performance, including the free hand. They are not wrist-goal arcs.
        if not a.angel:
            for side in ('l','r'):
                c,meta=captured(a,'SlapDownwards',side=='l','heavy')
                new['r32_berserk_'+side]=convert(a,original,c,'berserk_'+side,guard);data['sources']['berserk_'+side]=meta
            for label in ('jab','cross','hook','heavy'):
                side=new['r32_'+label]['leading_side'];c=copy.deepcopy(new['r32_berserk_'+side]);c['intent']='captured_downstrike';c['duration_seconds']=new['r32_'+label]['duration_seconds'];new['r32_low_'+label]=c
        for label,c in data['clips'].items():
            if label in new:continue
            # Extend every retained clip to the same rig order, including
            # jumps, locomotion and roar. Never leave a half-open old hand.
            updated=copy.deepcopy(c);updated['frames']=[]
            for f in c['frames']:
                p=decode(a,data,f)
                if not a.angel:hands.apply(p,a.rig.rig,.5 if label=='r32_berserk_roar' else 1)
                updated['frames'].append(record(a,p,f.get('foot_contact',[True,True])))
            new[label]=updated
        data.update(bones=a.names if a.angel else hands.names(a.rig.rig),clips=new,combat_foundation=36,choreography='captured_full_body_r36',hand_pose_revision=2)
        (OUT/file).write_text(json.dumps(data,separators=(',',':')),encoding='utf8');print('Authored full performance',key,flush=True)
if __name__=='__main__':main()
