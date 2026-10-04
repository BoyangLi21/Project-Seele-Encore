"""Dense contact and angular continuity audit of a captured arm candidate."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
from scipy.spatial.transform import Rotation as R
from author_captured_arm_support_r45 import Pose,reconcile_arm_goals
from scipy.spatial.transform import Slerp
from eva_native_arm_surface_r45 import arm_surfaces, deform


def interpolate(first, last, t):
    qa, qb = np.array(first['rotation_wxyz']), np.array(last['rotation_wxyz'])
    dot = (qa * qb).sum(1)
    qb = qb * np.where(dot < 0, -1, 1)[:, None]
    dot = np.clip(abs(dot), 0, 1); angle = np.arccos(dot); denominator = np.sin(angle)
    left = np.divide(np.sin((1-t)*angle), denominator, out=np.full(len(dot), 1-t), where=denominator > 1e-6)
    right = np.divide(np.sin(t*angle), denominator, out=np.full(len(dot), t), where=denominator > 1e-6)
    q = qa*left[:, None] + qb*right[:, None]; q /= np.linalg.norm(q, axis=1)[:, None]
    positions = {n: (np.array(v)*(1-t)+np.array(last['bone_position_xyz'].get(n, [0,0,0]))*t).tolist()
                 for n,v in first['bone_position_xyz'].items()}
    return dict(rotation_wxyz=q.tolist(), bone_position_xyz=positions,
                root_m=(np.array(first['root_m'])*(1-t)+np.array(last['root_m'])*t).tolist())


def main():
    p = argparse.ArgumentParser()
    for key in ('profile','mesh','support','out'):
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--world-arm-goals',action='store_true')
    p.add_argument('--physical',type=Path)
    a=p.parse_args();assert not a.out.exists()
    doc=json.loads(a.profile.read_text('utf8'));mesh=json.loads(a.mesh.read_text('utf8'))
    support=json.loads((a.support/'support_surface.json').read_text('utf8'))
    surfaces={s:arm_surfaces(mesh,s) for s in ('l','r')}
    hulls={s:np.array(support['hull_vertices'][s]) for s in ('l','r')}
    joints={}
    if a.world_arm_goals:
        assert a.physical
        definition=json.loads(a.physical.read_text('utf8'))['models']['1']['bodies']
        joints={side:np.array(next(r for r in definition if r['name']=='forearm_'+side)['joint']).reshape(4,4)[:3,3]/.2 for side in ('l','r')}
    rows=[];angular=[]
    for clip_name in ('to_prone','prone_hold','crawl','from_prone'):
        clip=doc['clips'][clip_name];frames=clip['frames'];dt=clip['duration_seconds']/(len(frames)-1)
        for index,first in enumerate(frames):
            if index+1<len(frames):
                last=frames[index+1]
                for name in ('clavicle_l','clavicle_r','arm_l','arm_r','forearm_l','forearm_r','hand_l','hand_r'):
                    bi=doc['bones'].index(name);qa=np.array(first['rotation_wxyz'][bi]);qb=np.array(last['rotation_wxyz'][bi])
                    angle=float(np.degrees(2*np.arccos(np.clip(abs(qa@qb),0,1))))
                    angular.append(dict(clip=clip_name,frame=index,bone=name,degrees=angle,interval_seconds=dt))
            else:last=first
            if a.world_arm_goals:
                first_pose,last_pose=Pose(doc,first),Pose(doc,last)
                goals={}
                for side in ('l','r'):
                    endpoints=[]
                    for point in (first_pose,last_pose):
                        m=point.matrix('arm_'+side)
                        endpoints.append((point.point('hand_'+side),m[:3,:3]@joints[side]+m[:3,3],R.from_matrix(point.matrix('hand_'+side)[:3,:3]).as_quat()))
                    goals[side]=endpoints
            for t in ((0.,.25,.5,.75) if index+1<len(frames) else (0.,)):
                pose=Pose(doc,first if not t else interpolate(first,last,t))
                for side in ('l','r'):
                    if a.world_arm_goals and t:
                        first_goal,last_goal=goals[side]
                        target=first_goal[0]*(1-t)+last_goal[0]*t
                        pole=first_goal[1]*(1-t)+last_goal[1]*t
                        orientation=Slerp([0,1],R.from_quat([first_goal[2],last_goal[2]]))([t])[0]
                        reconcile_arm_goals(pose,side,joints[side],target,orientation,pole)
                    arm,forearm,hand=['arm_'+side,'forearm_'+side,'hand_'+side]
                    matrices={n:pose.matrix(n)for n in (arm,forearm,hand)}
                    palms=hulls[side]@matrices[hand][:3,:3].T+matrices[hand][:3,3]
                    mins=[float(deform(surfaces[side][n],matrices)[:,1].min()*5)for n in (arm,forearm)]
                    mins.append(float(palms[:,1].min()*5))
                    rows.append(dict(clip=clip_name,frame=index,alpha=t,side=side,minima_m=mins,minimum_m=min(mins)))
        print('audited',clip_name,flush=True)
    failures=[r for r in rows if r['minimum_m']<0]
    result=dict(profile_sha256=hashlib.sha256(a.profile.read_bytes()).hexdigest(),
                actual_surface_side_samples=len(rows),penetration_samples=len(failures),
                worst_surface_samples=sorted(rows,key=lambda r:r['minimum_m'])[:15],
                worst_angular_steps=sorted(angular,key=lambda r:r['degrees'],reverse=True)[:20],
                world_space_contact_reconciliation=a.world_arm_goals,
                scope='Four samples per key interval; quaternion SLERP and complete measured arm/hand surfaces. Optional world-space wrist/pole restoration is explicit. Flat floor only, no self-collision or native acceptance.',
                dense_sampled_floor_clear=not failures,native_passed=False,art_accepted=False)
    a.out.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items()if k not in ['worst_surface_samples','worst_angular_steps']}))


if __name__=='__main__':main()
