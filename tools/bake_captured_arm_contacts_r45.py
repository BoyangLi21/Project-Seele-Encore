"""Bake low-pose arm contacts between keys, preserving source duration.

The intermediate wrist orientation, wrist goal and elbow guide interpolate
in body space, then the full current surfaces constrain the resulting pose.
This repairs a known-bad interpolation candidate; it never promotes it.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
from author_captured_arm_support_r45 import Pose,reconcile_arm_goals,fit_side
from audit_captured_arm_support_r45 import interpolate
from eva_native_arm_surface_r45 import arm_surfaces


def numeric_blend(a,b,t):
    if isinstance(a,dict):return {k:numeric_blend(v,b[k],t)for k,v in a.items()}
    if isinstance(a,list):return [numeric_blend(x,y,t)for x,y in zip(a,b)]
    return a*(1-t)+b*t


def main():
    p=argparse.ArgumentParser()
    for key in ('profile','mesh','physical','support','out'):
        p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--subdivisions',type=int,default=4)
    a=p.parse_args();assert 2<=a.subdivisions<=8 and not a.out.exists();a.out.mkdir(parents=True)
    doc=json.loads(a.profile.read_text('utf8'));assert doc['rig_key']==1
    mesh=json.loads(a.mesh.read_text('utf8'));support=json.loads((a.support/'support_surface.json').read_text('utf8'))
    replay=json.loads((a.support/'native_arm_replay.json').read_text('utf8'))
    assert support['actual_support_pose_reproduced'] and replay['verified']
    assert replay['source_mesh_sha256']==hashlib.sha256(a.mesh.read_bytes()).hexdigest()
    physical=json.loads(a.physical.read_text('utf8'))['models']['1']['bodies']
    joints={s:np.array(next(r for r in physical if r['name']=='forearm_'+s)['joint']).reshape(4,4)[:3,3]/.2 for s in ('l','r')}
    surfaces={s:arm_surfaces(mesh,s)for s in ('l','r')};hulls={s:np.array(support['hull_vertices'][s])for s in ('l','r')}
    changed=('clavicle_l','clavicle_r','arm_l','arm_r','forearm_l','forearm_r','hand_l','hand_r')
    rows=[];counts={}
    for clip_name in ('to_prone','prone_hold','crawl','from_prone'):
        clip=doc['clips'][clip_name];frames=clip['frames'];new=[]
        for index,first in enumerate(frames):
            last=frames[min(index+1,len(frames)-1)]
            first_pose,last_pose=Pose(doc,first),Pose(doc,last);goals={}
            for side in ('l','r'):
                endpoints=[]
                for pose in (first_pose,last_pose):
                    m=pose.matrix('arm_'+side)
                    endpoints.append((pose.point('hand_'+side),m[:3,:3]@joints[side]+m[:3,3],R.from_matrix(pose.matrix('hand_'+side)[:3,:3]).as_quat()))
                goals[side]=endpoints
            times=[i/a.subdivisions for i in range(a.subdivisions)]if index+1<len(frames)else [0.]
            for t in times:
                frame=copy.deepcopy(first)
                if t:
                    frame.update(interpolate(first,last,t))
                    for field in ('stage_root_blocks','stage_yaw_degrees','boot_contacts_body'):
                        frame[field]=numeric_blend(first[field],last[field],t)
                pose=Pose(doc,frame)
                for side in ('l','r'):
                    first_goal,last_goal=goals[side]
                    if t:
                        orientation=Slerp([0,1],R.from_quat([first_goal[2],last_goal[2]]))([t])[0]
                        reconcile_arm_goals(pose,side,joints[side],first_goal[0]*(1-t)+last_goal[0]*t,
                                            orientation,first_goal[1]*(1-t)+last_goal[1]*t)
                    _,result=fit_side(pose,side,joints[side],surfaces[side],hulls[side],np.zeros(3),np.radians(35),True)
                    rows.append(dict(clip=clip_name,original_frame=index,alpha=t,side=side,**result))
                for name in changed:
                    x,y,z,w=pose.rot[name].as_quat();frame['rotation_wxyz'][doc['bones'].index(name)]=[float(w),float(-x),float(-y),float(z)]
                    frame['bone_position_xyz'][name]=(pose.pos[name]*[-1,1,1]*16).tolist()
                new.append(frame)
            if index%90==0:print(clip_name,index,'failures',sum(not r['constraints_passed']for r in rows),flush=True)
        counts[clip_name]=dict(before=len(frames),after=len(new),unchanged_duration_seconds=clip['duration_seconds'])
        clip['frames']=new
    failures=sum(not r['constraints_passed']for r in rows)
    doc['actual_hand_support_r45']['intermediate_contact_bake']=dict(source_sha256=hashlib.sha256(a.profile.read_bytes()).hexdigest(),
        subdivisions=a.subdivisions,method='Body-space wrist/pole/orientation interpolation then current full-surface contact solve',
        original_duration_preserved=True,counts=counts,native_passed=False,dense_interpolation_passed=False)
    (a.out/a.profile.name).write_text(json.dumps(doc,separators=(',',':')),encoding='utf8')
    (a.out/'receipt.json').write_text(json.dumps(dict(counts=counts,surface_sides=len(rows),failures=failures,records=rows,
        native_passed=False,art_accepted=False,install_allowed=False),indent=2),encoding='utf8')
    if failures:(a.out/'INVALID_PIPELINE.json').write_text(json.dumps(dict(reason='Dense contact bake retained failed poses',failures=failures)),encoding='utf8')
    print('FINISHED',len(rows),'failures',failures,flush=True)


if __name__=='__main__':main()
