"""Remove inherited axial reversals without discontinuous per-frame IK.

Preserve the authored shoulder swing, elbow articulation, clocks, root travel
and damage. Smoothly limit axial roll over the complete affected curve. The
wrist moves with the corrected arm; weapon contact follows the actual rig.
"""
from pathlib import Path
import argparse
import copy
import json
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from calibrated_arm_r49 import axial_twist
from author_combat_bundle_r44 import maintain_joint_centres
from scipy.spatial.transform import Slerp


def repair_source_seams(clip,names):
    # The inherited joined Sword_A/B sources contain isolated near-bind frames
    # between the strike and recovery: a 60-130 degree one-frame reversal.
    # Replace only those finite discontinuity windows, not the full action.
    frames=clip['frames'];indices=[names.index(n)for n in ('arm_l','arm_r','forearm_l','forearm_r')]
    raw=np.asarray([f['rotation_wxyz']for f in frames]);peaks=np.zeros(len(frames)-1)
    for i in indices:
        q=R.from_quat(raw[:,i][:,[1,2,3,0]])
        peaks=np.maximum(peaks,np.degrees((q[:-1].inv()*q[1:]).magnitude()))
    bad=np.flatnonzero(peaks>50);windows=[]
    for j in bad:
        lo=max(0,int(j)-5);hi=min(len(frames)-1,int(j)+6)
        if windows and lo<=windows[-1][1]:windows[-1][1]=max(hi,windows[-1][1])
        else:windows.append([lo,hi])
    for lo,hi in windows:
        for name in ('clavicle_l','clavicle_r','arm_l','arm_r','forearm_l','forearm_r','wrist_l','wrist_r','hand_l','hand_r'):
            n=names.index(name);curve=Slerp([lo,hi],R.from_quat(raw[[lo,hi],n][:,[1,2,3,0]]))
            for i in range(lo+1,hi):frames[i]['rotation_wxyz'][n]=curve(i).as_quat()[[3,0,1,2]].tolist()
        # One isolated trajectory reset belongs to the same faulty seam.
        travel=np.asarray(clip['trajectory_m'])
        for i in range(lo+1,hi):
            if np.linalg.norm(travel[i]-(travel[i-1]+travel[i+1])/2)>.25:
                clip['trajectory_m'][i]=((travel[i-1]+travel[i+1])/2).tolist()
    return windows


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    common.BODY=json.loads((args.runtime/'eva_body_r44.json').read_text(encoding='utf-8'));common.NAMES=common.BODY['motion']['bones']
    report=[];unresolved=[]
    for key in range(3):
        actor=Actor(key);path=args.runtime/f'eva_gameplay_r44_{key}.json';source=args.out/f'before_{key}.json'
        if not source.exists():source.write_bytes(path.read_bytes())
        data=json.loads(source.read_text(encoding='utf-8'));names=data['bones'];indices={n:i for i,n in enumerate(names)}
        for clip_name,clip in data['clips'].items():
            seam_windows=repair_source_seams(clip,names)if key==2 and clip_name in('r32_sword_a','r32_sword_b')else[]
            changed=0;peak_before=0;peak_after=0
            curves={}
            for s in ('l','r'):
                axis=actor.elbows[s]-actor.P['arm_'+s]
                q=[R.from_quat([-f['rotation_wxyz'][indices['arm_'+s]][1],-f['rotation_wxyz'][indices['arm_'+s]][2],f['rotation_wxyz'][indices['arm_'+s]][3],f['rotation_wxyz'][indices['arm_'+s]][0]])for f in clip['frames']]
                roll=np.unwrap([axial_twist(x,axis)for x in q])
                if np.max(abs(roll))>np.radians(90):
                    # Smooth saturation affects the complete curve. A hard
                    # frame threshold would create a new shoulder snap.
                    limit=np.radians(68)
                    curves[s]=limit*np.tanh(roll/limit)
            for i,frame in enumerate(clip['frames']):
                needs=[]
                for s in ('l','r'):
                    w,x,y,z=frame['rotation_wxyz'][indices['arm_'+s]];twist=abs(np.degrees(axial_twist(R.from_quat([-x,-y,z,w]),actor.elbows[s]-actor.P['arm_'+s])))
                    peak_before=max(peak_before,twist)
                    if s in curves:needs.append(s)
                if not needs:continue
                pose=actor.rig.decode(frame,names);original=copy.deepcopy(pose)
                for side in needs:
                    upper='arm_'+side;axis=actor.elbows[side]-actor.P[upper];axis/=np.linalg.norm(axis)
                    old=pose.q[upper];roll=axial_twist(old,axis)
                    swing=old*R.from_rotvec(axis*roll).inv()
                    pose.setq(upper,swing*R.from_rotvec(axis*curves[side][i]))
                    actual=float(np.degrees(axial_twist(pose.q[upper],axis)))
                    if abs(actual)>75.0001:unresolved.append(dict(rig=key,clip=clip_name,frame=i,side=side,twist=actual))
                    peak_after=max(peak_after,abs(actual));changed+=1
                maintain_joint_centres(actor,pose)
                encoded=actor.rig.encode(pose,frame.get('foot_contact',(False,False)),names)
                frame.update({k:encoded[k]for k in ('rotation_wxyz','bone_position_xyz','root_m')})
            if changed or seam_windows:report.append(dict(rig=key,clip=clip_name,repaired_arm_samples=changed,maximum_source_twist=peak_before,maximum_repaired_twist=peak_after,source_seam_windows=seam_windows))
        (args.out/f'eva_gameplay_r44_{key}.json').write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    serial=json.dumps(dict(changed=report,unresolved=unresolved,damage_or_timing_changed=False,native=False,art_accepted=False),indent=2,default=lambda v:bool(v)if isinstance(v,np.bool_)else float(v))
    (args.out/'REPORT.json').write_text(serial,encoding='utf-8')
    print('Repaired clips:',len(report),'Unresolved arm frames:',len(unresolved))


if __name__=='__main__':main()
