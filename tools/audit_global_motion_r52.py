"""Local joint and world bone rotation increments are measured separately."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
from r52_motion_core import selected,read
from author_finisher_r52 import world

def main():
    ap=argparse.ArgumentParser()
    for n in ('body','assets','angel-rig','clip','out'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();b,h,e=selected(a.body,a.assets,a.angel_rig);d=read(a.clip);names=['root','torso_lower','torso_upper','head','arm_l','forearm_l','hand_l','arm_r','forearm_r','hand_r','leg_l','shin_l','foot_l','leg_r','shin_r','foot_r'];report={}
    for role,rig in [('eva',h),('angel',e)]:
        values=[];positions=[]
        for i,f in enumerate(d[role]['frames']):
            p=rig.decode(f,d[role]['bones']);values.append([R.from_matrix(p.matrix(n)[:3,:3]).as_quat() for n in names]);root=np.asarray(d[role]['root_blocks'][i]);positions.append([world(p,root,n) for n in names])
        q=np.asarray(values);step=2*np.degrees(np.arccos(np.clip(np.abs((q[1:]*q[:-1]).sum(-1)),0,1)));maxima={n:float(step[:,j].max()) for j,n in enumerate(names)}
        top=[]
        for i,j in zip(*np.where(step>15)):top.append({'frame':int(i+1),'bone':names[j],'global_jump_deg':float(step[i,j])})
        displacement=np.linalg.norm(np.diff(np.asarray(positions),axis=0),axis=2);translation={}
        for j,n in enumerate(names):
            i=int(displacement[:,j].argmax());translation[n]={'max_blocks_frame':float(displacement[i,j]),'frame':i+1,'neighbour_steps':displacement[max(0,i-2):i+3,j].tolist()}
        report[role]={'max_global_jump_deg_frame':float(step.max()),'max_global_speed_deg_s':float(step.max()*d['fps']),'by_bone_jump_deg':maxima,'global_jumps_over_15_deg_frame':top,'actual_joint_world_position_steps':translation}
    a.out.write_text(json.dumps({'clip':str(a.clip.resolve()),'sha256':hashlib.sha256(a.clip.read_bytes()).hexdigest(),'fps':d['fps'],'measurement':'World orientation from complete parent bone matrices; differs from relative wrist quaternion when parent turns oppositely','actors':report,'native_verified':False,'user_accepted':False},indent=2),encoding='utf-8')
    print({r:(v['max_global_jump_deg_frame'],v['max_global_speed_deg_s']) for r,v in report.items()},flush=True)
if __name__=='__main__':main()
