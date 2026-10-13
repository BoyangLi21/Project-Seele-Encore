"""Actual selected clip motion audit. Rotation statistics and FK are separate."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
from r52_motion_core import selected, read, UNIT, MIRROR

def main():
    ap=argparse.ArgumentParser()
    for key in ('body','assets','angel-rig','clip','out'):ap.add_argument('--'+key,type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    body,hero,alien=selected(a.body,a.assets,a.angel_rig);d=read(a.clip);fps=d['fps'];report={}
    for role,rig,mirror in [('eva',hero,MIRROR),('angel',alien,np.ones(3))]:
        doc=d[role];raw=np.asarray([f['rotation_wxyz'] for f in doc['frames']]);qs=raw[:,:,[1,2,3,0]];qs[:,:,[0,1]]*=-1
        bybone={};max_perframe=np.zeros(len(raw)-1)
        for j,n in enumerate(doc['bones']):
            rr=R.from_quat(qs[:,j]);angles=np.degrees((rr[0].inv()*rr).magnitude());step=np.degrees((rr[:-1].inv()*rr[1:]).magnitude());max_perframe=np.maximum(max_perframe,step)
            bybone[n]={'excursion_from_frame0_deg':float(angles.max()),'angular_path_deg':float(step.sum()),'max_speed_deg_s':float(step.max()*fps),'p95_speed_deg_s':float(np.percentile(step*fps,95)),'moving_fraction_over_0_02_deg_frame':float(np.mean(step>.02))}
        sockets={};roots=np.asarray(doc['root_blocks'])
        for n in ('hand_l','hand_r','foot_l','foot_r'):
            local=np.asarray([rig.decode(f,doc['bones']).point(n)*mirror*UNIT for f in doc['frames']]);world=local+roots
            sockets[n]={'local_range_blocks':np.ptp(local,axis=0).tolist(),'world_range_blocks':np.ptp(world,axis=0).tolist(),'max_speed_local_blocks_s':float(np.linalg.norm(np.diff(local,axis=0),axis=1).max()*fps),'max_speed_world_blocks_s':float(np.linalg.norm(np.diff(world,axis=0),axis=1).max()*fps)}
        windows=[]
        for s,e in [(0,3),(3,5.1),(5.1,8.5),(8.5,11.05),(11.05,15.2),(15.2,16.6),(16.6,18.6),(18.6,23)]:
            i,j=round(s*fps),round(e*fps);step=max_perframe[i:j]
            windows.append({'seconds':[s,e],'frames':j-i,'any_body_rotation_fraction_over_0_02_deg':float(np.mean(step>.02)),'max_body_speed_deg_s':float(step.max()*fps),'root_translation_blocks':float(np.linalg.norm(np.diff(roots[i:j+1],axis=0),axis=1).sum())})
        report[role]={'frames':len(raw),'bones':len(doc['bones']),'bone_statistics':bybone,'fk_joint_statistics':sockets,'windows':windows,'static_body_fraction_over_all_bones':float(np.mean(max_perframe<=.02))}
    payload={'source':str(a.clip.resolve()),'sha256':hashlib.sha256(a.clip.read_bytes()).hexdigest(),'fps':fps,'duration_ticks':d['duration_ticks'],'measurement':'Quaternion shortest angular increments; FK uses actual selected bind pivots and encoded root_m, no runtime rendering assumptions','actors':report,'native_verified':False,'user_accepted':False}
    (a.out/'MATERIAL_AUDIT.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    for role,p in report.items():print(role,'static fraction',round(p['static_body_fraction_over_all_bones'],3),'hands local ranges',p['fk_joint_statistics']['hand_r']['local_range_blocks'])
    print(json.dumps({k:v['windows'] for k,v in report.items()},indent=2))
if __name__=='__main__':main()
