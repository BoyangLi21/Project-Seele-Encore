"""Measured original source cycles and seams, independent of author IK."""
from pathlib import Path
import json,numpy as np
from scipy.spatial.transform import Rotation as R
from bvh_motion_r12 import load_bvh

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat/source_C5_normal_review_v1';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'external-assets/incoming/mocap/accad-eva-seed-r01/third_party_normalized/source_extract/male2_bvh'

def read(file):
    d=load_bvh(SOURCE/file);names=d['names'];hips=names.index('Hips');positions=d['positions']*.01
    q=d['rotations'];local=np.empty_like(q)
    for i,parent in enumerate(d['parents']):local[:,i]=q[:,i]if parent<0 else(R.from_quat(q[:,parent]).inv()*R.from_quat(q[:,i])).as_quat()
    relative=np.einsum('fij,fbj->fbi',R.from_quat(q[:,hips]).inv().as_matrix(),positions-positions[:,hips:hips+1])
    feet=np.asarray([np.minimum(positions[:,names.index(side+'ToeBase'),1],positions[:,names.index(side+'ToeBase_End'),1])for side in ('Left','Right')]).T
    return d,local,relative,feet,positions

def pair(file,first,last):
    d,q,p,feet,positions=read(file);dot=np.abs((q[first]*q[last]).sum(1));angles=np.degrees(2*np.arccos(np.clip(dot,0,1)));i=int(angles.argmax())
    return dict(file=file,original_frames=[first,last],source_fps=d['fps'],interval_seconds=(last-first)/d['fps'],
                maximum_local_angle_degrees=float(angles[i]),worst_joint=d['names'][i],
                lower_body_local_angles={n:float(angles[d['names'].index(n)])for n in ('LeftUpLeg','LeftLeg','LeftFoot','RightUpLeg','RightLeg','RightFoot')},
                feet_height_metres=[feet[first].tolist(),feet[last].tolist()],contact_signature=[(feet[first]<.09).tolist(),(feet[last]<.09).tolist()],
                maximum_hip_relative_joint_displacement_metres=float(np.linalg.norm(p[last]-p[first],axis=1).max()))

rows=[pair('Male2_C5_WalkToRun.bvh',44,45),pair('Male2_B3_Walk.bvh',189,309),pair('Male2_C3_Run.bvh',27,50)]
search=[]
for file,first,last in [('Male2_B3_Walk.bvh',189,309),('Male2_C3_Run.bvh',27,50)]:
    d,q,p,feet,positions=read(file);width=last-first;candidates=[]
    for begin in range(max(0,first-45),min(len(q)-width,first+46)):
        end=begin+width;angles=np.degrees(2*np.arccos(np.clip(np.abs((q[begin]*q[end]).sum(1)),0,1)))
        body=[i for i,n in enumerate(d['names'])if n in ('LeftUpLeg','LeftLeg','LeftFoot','RightUpLeg','RightLeg','RightFoot','LeftArm','LeftForeArm','RightArm','RightForeArm')]
        displacement=np.linalg.norm(p[end]-p[begin],axis=1);same=np.array_equal(feet[begin]<.09,feet[end]<.09)
        candidates.append(dict(original_frames=[begin,end],original_cycle_interval_seconds=width/d['fps'],maximum_joint_angle_degrees=float(angles[body].max()),
                               hip_relative_max_displacement_metres=float(displacement.max()),same_contact_signature=bool(same),score=float(angles[body].mean()+100*displacement.mean()+(0 if same else 100))))
    search.append(dict(file=file,search='Shift the whole existing-duration window by up to45 original frames; duration unchanged',best=sorted(candidates,key=lambda r:r['score'])[:6],production_chosen=False))
report=dict(observed_original_source=rows,same_duration_endpoint_search=search,
            original_interval_is_seamless_loop=False,quality='Source angles and phase closure are measurements, not acceptance. Visual full-speed source and whole EVA playback remain necessary.')
(OUT/'source_phase_seam_audit.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report,indent=2))
