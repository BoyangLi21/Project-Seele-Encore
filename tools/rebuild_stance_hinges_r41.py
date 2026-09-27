"""Reconstruct low-stance IK branches from their continuous end-effector paths.

Keep the existing foot paths and world orientations;
transport each thigh's previous anatomical frame instead of accepting arbitrary
ball-joint IK branch changes from the old export, then redistribute motion
inside each stance interval. Write a candidate only.
"""
from pathlib import Path
import copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R,Slerp
from author_combat_r35 import Actor
from study_combat_performance_r36 import decode

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/spatial_repair_r41/stance_candidate'


def swing(a,b):
    a=np.asarray(a,float);a/=np.linalg.norm(a);b=np.asarray(b,float);b/=np.linalg.norm(b)
    axis=np.cross(a,b);length=np.linalg.norm(axis);dot=np.clip(a@b,-1,1)
    if length<1e-9:
        if dot>0:return R.identity()
        axis=np.array([1.,0,0]);axis-=a*(axis@a);axis/=np.linalg.norm(axis);return R.from_rotvec(axis*np.pi)
    return R.from_rotvec(axis/length*np.arctan2(length,dot))


def reconstruct(actor,pose,side,target,orientation,previous):
    upper,lower,end='leg_'+side,'shin_'+side,'foot_'+side
    pose.setq(upper,previous)
    pose.setq('ankle_'+side,R.identity())
    joint=actor.knees[side];u=joint-actor.P[upper];v=actor.P[end]-joint;axis=np.array([-1.,0,0])
    parallel=axis*(axis@v);perpendicular=v-parallel
    a=u@perpendicular;b=u@np.cross(axis,v);c=u@parallel;amp=np.hypot(a,b);neutral=np.arctan2(b,a)
    la=np.linalg.norm(u);lb=np.linalg.norm(v)
    maximum=np.sqrt(la*la+lb*lb+2*(amp+c))*.9999
    minimum=np.sqrt(max(0,la*la+lb*lb+2*(a*np.cos(2.62)+b*np.sin(2.62)+c)))+.0001
    origin=pose.point(upper);direction=target-origin;length=np.clip(np.linalg.norm(direction),minimum,maximum);direction/=np.linalg.norm(direction)
    angle=neutral+np.arccos(np.clip(((length*length-la*la-lb*lb)/2-c)/max(amp,1e-8),-1,1))
    hinge=R.from_rotvec(axis*angle)
    authored=R.from_matrix(pose.matrix(upper)[:3,:3]);reach=authored.apply(u+hinge.apply(v))
    world=swing(reach,direction)*authored
    pose.setq(upper,R.from_matrix(pose.parent(upper)[:3,:3]).inv()*world)
    pose.setq(lower,hinge);offset=joint-actor.P[lower];pose.setp(lower,offset-hinge.apply(offset))
    pose.setq(end,R.from_matrix(pose.parent(end)[:3,:3]).inv()*orientation)
    return float(np.linalg.norm(pose.point(end)-target))


def reachable_root(actor,pose,targets):
    for _ in range(20):
        changed=False
        for side in ('l','r'):
            u=actor.knees[side]-actor.P['leg_'+side];v=actor.P['foot_'+side]-actor.knees[side];axis=np.array([-1.,0,0])
            parallel=axis*(axis@v);perpendicular=v-parallel
            a=u@perpendicular;b=u@np.cross(axis,v);c=u@parallel;amp=np.hypot(a,b)
            maximum=np.sqrt(u@u+v@v+2*(amp+c))*.9995
            minimum=np.sqrt(max(0,u@u+v@v+2*(a*np.cos(2.62)+b*np.sin(2.62)+c)))+.002
            d=pose.point('leg_'+side)-targets[side];length=np.linalg.norm(d);wanted=np.clip(length,minimum,maximum)
            if abs(length-wanted)>.0001:
                pose.setp('root',pose.p['root']+d/max(length,1e-8)*(wanted-length));changed=True
        if not changed:break


def deltas(frames,names):
    q=np.asarray([f['rotation_wxyz'] for f in frames]);q/=np.linalg.norm(q,axis=2,keepdims=True)
    angles=np.degrees(2*np.arccos(np.clip(np.abs((q[:-1]*q[1:]).sum(2)),0,1)))
    ids=[i for i,n in enumerate(names) if n.startswith(('leg_','shin_','ankle_','foot_'))]
    at=np.unravel_index(np.argmax(angles[:,ids]),angles[:,ids].shape)
    return dict(max_degrees=float(angles[at[0],ids[at[1]]]),frame=int(at[0]),bone=names[ids[at[1]]])


def pace(frames,names):
    """Redistribute motion inside each stance interval, retaining its endpoints."""
    q=np.asarray([f['rotation_wxyz'] for f in frames]);q/=np.linalg.norm(q,axis=2,keepdims=True)
    angles=2*np.arccos(np.clip(np.abs((q[:-1]*q[1:]).sum(2)),0,1))
    ids=[i for i,n in enumerate(names) if n.startswith(('leg_','shin_','ankle_','foot_','arm_','forearm_','torso_','wrist_','hand_'))]
    cost=np.maximum(.002,angles[:,ids].max(1));sample=[]
    for segment in range(3):
        begin=segment*60;distance=np.r_[0,np.cumsum(cost[begin:begin+60])]
        t=np.linspace(0,1,61);smooth=t*t*t*(10-15*t+6*t*t)
        at=np.interp(smooth*distance[-1],distance,np.arange(begin,begin+61))
        sample.extend(at if segment==0 else at[1:])
    output=[]
    for at in sample:
        i=int(at);j=min(i+1,len(frames)-1);t=at-i;qa=q[i];qb=q[j].copy()
        dot=(qa*qb).sum(1);qb[dot<0]*=-1;dot=np.abs(dot);theta=np.arccos(np.clip(dot,-1,1));sine=np.sin(theta)
        weights=np.where(sine>1e-7,np.sin((1-t)*theta)/np.maximum(sine,1e-7),1-t)
        other=np.where(sine>1e-7,np.sin(t*theta)/np.maximum(sine,1e-7),t)
        result=qa*weights[:,None]+qb*other[:,None];result/=np.linalg.norm(result,axis=1,keepdims=True)
        positions={}
        for name in set(frames[i].get('bone_position_xyz',{}))|set(frames[j].get('bone_position_xyz',{})):
            a=np.asarray(frames[i].get('bone_position_xyz',{}).get(name,[0,0,0]));b=np.asarray(frames[j].get('bone_position_xyz',{}).get(name,[0,0,0]));positions[name]=(a*(1-t)+b*t).tolist()
        root=(np.asarray(frames[i]['root_m'])*(1-t)+np.asarray(frames[j]['root_m'])*t).tolist()
        output.append(dict(root_m=root,rotation_wxyz=result.tolist(),bone_position_xyz=positions,foot_contact=frames[i].get('foot_contact',[True,True])))
    return output


def hand_frame(along,back):
    y=np.asarray(along,float);y/=np.linalg.norm(y)
    z=np.asarray(back,float);z-=y*(z@y);z/=np.linalg.norm(z)
    return np.column_stack((np.cross(y,z),y,z))


def supporting_palms(actor,poses,stance=True):
    # Bake one continuous world-space wrist path. Blending an instantaneous
    # target onto each moving source pose changes quaternion branches near
    # 180 degrees and produced a visible 145-degree flip in native review.
    goals={};curves={}
    for side in ('l','r'):
        name='hand_'+side
        along=actor.P['finger_middle_'+side]-actor.P[name];along/=np.linalg.norm(along)
        adapter=actor.rig.rig['finger_middle_axis_'+side]
        bind=R.from_euler('xyz',np.asarray(adapter.get('rotation',[0,0,0]))*[-1,-1,1],degrees=True)
        extended=np.arctan2(along@bind.apply([1,0,0]),along@bind.apply([0,-1,0]))
        back=-(bind*R.from_euler('z',extended)).apply([1,0,0])
        if 'r30_hand_frame_'+side in actor.P:back=np.array([0.,0.,1.])
        # Mirrored TV hands have opposite palm frames. Assigning the same
        # index-to-little cross product to both had left one palm facing up.
        rest=hand_frame(along,back)
        goals[side]=R.from_matrix(hand_frame([0,0,-1],[0,1,0])@rest.T)
        if stance:
            start=R.from_matrix(poses[60].matrix(name)[:3,:3]);curves[side]=Slerp([0,1],R.concatenate([start,goals[side]]))
    for i,pose in enumerate(poses):
        if stance and i<=60:continue
        t=np.clip((i-60)/60,0,1);t=t*t*t*(10-15*t+6*t*t)
        for side in ('l','r'):
            name='hand_'+side;world=curves[side]([t])[0] if stance else goals[side]
            pose.setq(name,R.from_matrix(pose.parent(name)[:3,:3]).inv()*world)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    baseline=OUT/'baseline_eva_body_r25.json'
    if not baseline.exists():baseline.write_bytes((ROOT/'run/projectseele-local-maps/eva_body_r25.json').read_bytes())
    raw=baseline.read_bytes();data=json.loads(raw);candidate=copy.deepcopy(data);motion=data['motion'];summary=[]
    assert 'stance_clips_by_rig' not in data,'Do not recursively author the new result'
    reference=Actor(1);reference_height=reference.height
    reference_width=abs(reference.P['foot_l'][0]);reference_feet={s:reference.P['foot_'+s].copy() for s in ('l','r')}
    reference_paths={}
    for label in ['unarmed_stance','rifle_stance']:
        paths=[]
        for frame in motion['clips'][label]['frames']:
            p=decode(reference,motion,frame);feet={}
            for side in ('l','r'):
                orientation=R.from_matrix(p.matrix('foot_'+side)[:3,:3]);point=p.point('foot_'+side).copy()
                feet[side]=(point,orientation,float(point[1]+orientation.apply(reference.feet[side])[:,1].min()))
            paths.append(feet)
        reference_paths[label]=paths
    replacements={}
    for key in range(5):
        actor=Actor(key);names=list(actor.rig.rig);clips={}
        for label in ['unarmed_stance','rifle_stance']:
            original=motion['clips'][label];poses=[decode(actor,motion,f) for f in original['frames']]
            if label=='unarmed_stance':supporting_palms(actor,poses)
            seed=decode(actor,motion,motion['clips']['idle']['frames'][0])
            previous={s:seed.q['leg_'+s] for s in ('l','r')};frames=[];error=0
            for frame_index,pose in enumerate(poses):
                targets={};orientations={};ratio=actor.height/reference_height
                if key>=3:pose.setp('root',pose.p['root']*ratio)
                for side in ('l','r'):
                    if key<3:
                        targets[side]=pose.point('foot_'+side).copy();orientations[side]=R.from_matrix(pose.matrix('foot_'+side)[:3,:3])
                    else:
                        source,orientation,gap=reference_paths[label][frame_index][side]
                        target=source*ratio
                        target[0]=source[0]*abs(actor.P['foot_'+side][0])/reference_width
                        target[2]+=actor.P['foot_'+side][2]-reference_feet[side][2]*ratio
                        target[1]=gap*ratio-orientation.apply(actor.feet[side])[:,1].min()
                        targets[side]=target;orientations[side]=orientation
                reachable_root(actor,pose,targets)
                for side in ('l','r'):
                    error=max(error,reconstruct(actor,pose,side,targets[side],orientations[side],previous[side]))
                    previous[side]=pose.q['leg_'+side]
                frames.append(actor.rig.encode(pose,(True,True),names))
            reconstructed=deltas(frames,names);frames=pace(frames,names)
            clips[label]=dict(duration_seconds=original['duration_seconds'],loop=False,frames=frames)
            summary.append(dict(rig=key,clip=label,before=deltas(original['frames'],motion['bones']),after_reconstruction=reconstructed,after=deltas(frames,names),max_foot_target_error_blocks_before_resampling=error*5/16))
        original=motion['clips']['prone_crawl'];poses=[decode(actor,motion,f) for f in original['frames']]
        supporting_palms(actor,poses,False)
        clips['prone_crawl']={**original,'frames':[actor.rig.encode(p,tuple(f.get('foot_contact',[True,True])),names) for p,f in zip(poses,original['frames'])]}
        replacements[str(key)]=dict(bones=names,clips=clips)
        print('Reconstructed low stances for rig',key,flush=True)
    candidate['stance_clips_by_rig']=replacements
    candidate['stance_revision_r41']=dict(source_sha256=hashlib.sha256(raw).hexdigest(),method='Continuous thigh frame, anatomical knee hinge and per-rig retargeting; original foot paths/world orientation retained; arc-length pacing inside fixed stance endpoints',candidate=True)
    (OUT/'eva_body_r41.json').write_text(json.dumps(candidate,separators=(',',':')),'utf8')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),'utf8')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
