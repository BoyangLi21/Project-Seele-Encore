"""Validate the actual candidate bundle, not a parallel source construction.

This is an offline structure/kinematics check. Native final-bone and vertex
capture, slopes, interrupted actions, latency and artistic review are separate.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from scipy.spatial.transform import Rotation as R

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'artifacts/rebuild_r44/combat/motion'


class Pose:
    def __init__(self,rig,names,frame):
        self.rig={b['name']:b for b in rig};self.P={n:np.asarray(b['pivot'],float)*[-1,1,1] for n,b in self.rig.items()}
        self.q={n:R.identity() for n in self.rig};self.p={n:np.zeros(3) for n in self.rig};self.cache={}
        for n,(w,x,y,z) in zip(names,frame['rotation_wxyz']):self.q[n]=R.from_quat([-x,-y,z,w])
        for n,v in frame.get('bone_position_xyz',{}).items():self.p[n]=np.asarray(v)*[-1,1,1]
        self.p['root']=np.asarray(frame['root_m'])*112*[-1,1,1]
    def matrix(self,name):
        if name in self.cache:return self.cache[name]
        p=self.P[name];q=self.q[name].as_matrix();m=np.eye(4);m[:3,:3]=q;m[:3,3]=self.p[name]+p-q@p
        parent=self.rig[name].get('parent');m=self.matrix(parent)@m if parent else m
        self.cache[name]=m;return m
    def point(self,name,point):
        return (self.matrix(name)@np.r_[point,1])[:3]


def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bundle',type=Path,default=DEFAULT);args=ap.parse_args();directory=args.bundle
    manifest=json.loads((directory/'combat_bundle_r44.json').read_text('utf8'));errors=[];reports=[]
    required=['eva_body_r44.json','first_battle_r44.json','sachiel_gameplay_r44.json']+[f'eva_gameplay_r44_{key}.json' for key in range(5)]
    for name in required:
        file=directory/name
        if not file.is_file() or manifest['files'].get(name)!=sha(file):errors.append(dict(file=name,error='Required bundle file is missing or its SHA differs'))
    body=json.loads((directory/'eva_body_r44.json').read_text('utf8'))
    for key in range(5):
        file=directory/f'eva_gameplay_r44_{key}.json'
        if not file.is_file():continue
        data=json.loads(file.read_text('utf8'));rig=body['rigs'][str(key)];names=data['bones']
        if data['rig_key']!=key or data.get('rig_contract_r44')!=rig:errors.append(dict(rig=key,error='Gameplay and body characterize different rigs'))
        if len(set(names))!=len(names) or set(names)!={b['name'] for b in rig}:errors.append(dict(rig=key,error='Incomplete/duplicate channels'))
        clips=[]
        for label,clip in data['clips'].items():
            frames=clip['frames'];q=np.asarray([f['rotation_wxyz'] for f in frames],float)
            finite=np.isfinite(q).all() and q.shape[1:]==(len(names),4)
            norm=np.linalg.norm(q,axis=2)
            if not finite or np.max(abs(norm-1))>2e-6:errors.append(dict(rig=key,clip=label,error='Invalid quaternion contract'))
            normalized=q/np.maximum(norm[...,None],1e-12)
            angles=np.degrees(2*np.arccos(np.clip(abs((normalized[1:]*normalized[:-1]).sum(2)),0,1)))
            selected=[i for i,n in enumerate(names) if n.startswith(('arm_','forearm_','leg_','shin_','hand_','wrist_')) or n in ('root','torso_lower','torso_upper')]
            worst=float(angles[:,selected].max()) if len(angles) else 0
            row=dict(clip=label,frames=len(frames),duration=clip['duration_seconds'],max_body_step_degrees=worst,contact_phase=clip.get('contact_phase'))
            low_action=label.startswith(('r32_crouch_','r32_prone_'))
            if low_action and (not clip.get('adaptation_r44') or clip.get('contact_bone') not in names or not 0<float(clip.get('contact_phase',-1))<1):
                errors.append(dict(rig=key,clip=label,error='Low action is missing source/phase/contact contract'))
            if label in ('r32_guard','r32_jab','r32_cross','r32_hook','r32_heavy','r32_knife_forward','r32_knife_reverse','r32_kick') or low_action:
                joints=0.;axisError=0.;gripDots=[]
                minimum_body=1e9
                for f in frames:
                    pose=Pose(rig,names,f)
                    for side in ('l','r'):
                        for upper,lower,marker,offset in [('arm_','forearm_','r30_elbow_socket_',None),('leg_','shin_','r30_knee_socket_',np.array([0,11.4,0]))]:
                            joint=pose.P.get(marker+side)
                            if joint is None:
                                joint=pose.P[lower+side]+offset if offset is not None else np.array([-23.489652 if side=='l' else 23.489652,123.435069,7.737214])
                            joints=max(joints,float(np.linalg.norm(pose.point(upper+side,joint)-pose.point(lower+side,joint))))
                            xyzw=pose.q[lower+side].as_quat();axisError=max(axisError,float(np.linalg.norm(xyzw[1:3])))
                    if 'knife_' in label:
                        tip=np.asarray(clip['contact_point_model'])*[-1,1,1]
                        grip=pose.P['knife']
                        direction=pose.point('knife',tip)-pose.point('knife',grip)
                        forearm=pose.point('hand_r',pose.P['hand_r'])-pose.point('forearm_r',pose.P.get('r30_elbow_socket_r',np.array([23.489652,123.435069,7.737214])))
                        gripDots.append(float(direction@forearm/max(np.linalg.norm(direction)*np.linalg.norm(forearm),1e-9)))
                    if low_action:
                        support=body.get('rig_support',{}).get(str(key),body['support'])
                        for bone,vertices in support.items():
                            matrix=pose.matrix(bone);minimum_body=min(minimum_body,float((np.asarray(vertices)@matrix[1,:3]+matrix[1,3]).min()))
                row.update(max_joint_gap_model_units=joints,max_hinge_off_axis=axisError)
                if joints>1e-3 or axisError>1e-5:errors.append(dict(rig=key,clip=label,error='Anatomical joint/hinge contract failed',gap=joints,axis_error=axisError))
                if gripDots:row['median_blade_forearm_dot']=float(np.median(gripDots))
                if worst>35:errors.append(dict(rig=key,clip=label,error='Candidate body channel jumps over 35 degrees/frame',degrees=worst))
                if low_action:
                    row['minimum_body_floor_model_units']=minimum_body
                    if minimum_body<-.025:errors.append(dict(rig=key,clip=label,error='Low bearing mesh crosses the source ground plane',minimum=minimum_body))
            clips.append(row)
        reports.append(dict(rig=key,channels=len(names),clips=clips))
    first=json.loads((directory/'first_battle_r44.json').read_text('utf8'))
    if first['duration_ticks']!=460 or len(first['eva']['frames'])!=691:errors.append(dict(file='first_battle_r44.json',error='Paired timeline contract'))
    result=dict(bundle=manifest['bundle_id'],functional_offline_pass=not errors,errors=errors,rigs=reports,
                first_battle=first.get('r44_articulation'),
                scope='Read-back of candidate files: SHA, profile indices, complete channels, quaternion/translation structure, mathematical anatomical joints; no actual game images inferred',
                unverified=['Actual client/server loaded hashes', 'Final rendered bones and skinned vertices', 'Knife/kick damage timing under synchronization changes',
                            'Slope/wall obstacles and reaction interrupts', 'First-battle paired wrap/arm contact and terminal red-to-black eyes', 'Visual acceptance'])
    target=directory.parent/'candidate_validation.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(bundle=result['bundle'],pass_=not errors,errors=errors,report=str(target)),ensure_ascii=False),flush=True)
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
