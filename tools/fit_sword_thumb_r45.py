"""Oppose the thumb onto the real handle, keeping the knife/fist poses unchanged."""
from pathlib import Path
import argparse,json,shutil
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation as R
from eva_hand_rig_math_r45 import controls,matrices,joint_points
from rebind_anatomical_hand_r45 import dq_pose

def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();shutil.copytree(a.candidate,a.out)
    file=a.out/'hand_rig_contract.json';c=json.loads(file.read_text());h=c['hands']['r'];g=json.loads((a.out/'eva_unit02.geo.json').read_text())
    mesh=json.loads((a.out/'eva_unit02_anatomical_hands_r45.mesh.json').read_text());part=mesh['parts']['hand_r'];skin=mesh['jointSkins']['hand_r'];raw=np.array(part['vertices']).reshape(-1,8)
    points=(raw[:,:3]+part['pivot'])*[-1,1,1]/16;palette=list(skin['influences']);weights=np.array([skin['influences'][n]for n in palette]).T
    inverse=[np.array(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette];pose=controls(c,'sword_right','r');thumb=h['digits']['thumb']['joints']
    thumb_names=[j['name']for j in thumb];ids=np.flatnonzero(sum(weights[:,palette.index(n)]for n in thumb_names)>.75)
    d=np.load(a.out/'sword_grip_preview.npz');weapon=d['sword'];N=np.array(h['palmar_normal_bind']);L=np.array(h['longitudinal_bind']);k=c['sword_attachment_r45']
    axis=-R.from_quat(k['rotation_xyzw']).as_matrix()[:,1];centre=np.array(k['target_handle_centre'])
    shaft=weapon[np.abs((weapon-centre)@axis)<.60];shaft_hull=ConvexHull(shaft).equations
    index_axis=(np.array(h['digits']['index']['joints'][0]['head_bind'])-centre)@axis
    target=centre+axis*(index_axis+.11)+N*.10
    index_names=[j['name']for j in h['digits']['index']['joints']];index_ids=np.flatnonzero(sum(weights[:,palette.index(n)]for n in index_names)>.65)
    index_hull=ConvexHull(d['hand'][index_ids]).equations
    fields=[(0,0),(0,1),(0,2),(1,0),(2,0)];x0=np.array([pose[thumb_names[i]][j]for i,j in fields]);lo=np.array([thumb[i]['anatomical_limits_degrees'][j][0]for i,j in fields]);hi=np.array([thumb[i]['anatomical_limits_degrees'][j][1]for i,j in fields])
    def sample(x,full=False):
        values={n:q.copy()for n,q in pose.items()}
        for v,(i,j)in zip(x,fields):values[thumb_names[i]][j]=v
        ms=matrices(g,c,'r',values);transforms=[ms[n]@iv for n,iv in zip(palette,inverse)]
        surface=dq_pose(points if full else points[ids],weights if full else weights[ids],transforms)
        last=thumb[-1];tip=(ms[last['name']]@np.array(last['inverse_bind_column_major']).reshape(4,4).T@np.r_[last['tip_bind'],1])[:3]
        return surface,tip,values
    def residual(x):
        surface,tip,_=sample(x);solid=(surface@shaft_hull[:,:3].T+shaft_hull[:,3]).max(1);other=(surface@index_hull[:,:3].T+index_hull[:,3]).max(1)
        return np.r_[np.maximum(.005-solid,0)*90,np.maximum(.004-other,0)*70,(tip-target)*12,(x-x0)*.0004]
    starts=[x0,np.clip(x0+[-15,20,20,0,-15],lo,hi),np.clip(x0+[10,-20,-20,-15,-15],lo,hi)]
    fits=[least_squares(residual,np.clip(x,lo+1e-5,hi-1e-5),bounds=(lo,hi),max_nfev=180,diff_step=1e-4)for x in starts];fit=min(fits,key=lambda r:np.linalg.norm(r.fun));surface,tip,values=sample(fit.x,True)
    c['pose_controls']['sword_right']['thumb']=[values[n].tolist()for n in thumb_names]
    c['sword_thumb_fit_r45']=dict(angles=c['pose_controls']['sword_right']['thumb'],target=target.tolist(),tip=tip.tolist(),tip_error_native=float(np.linalg.norm(tip-target)),visual_accepted=False)
    assert all(np.allclose(controls(c,'sword_right','r')[n],v)for n,v in values.items())
    file.write_text(json.dumps(c,indent=2));np.savez_compressed(a.out/'sword_grip_preview.npz',hand=surface,sword=weapon,normal=N,along=L);print(json.dumps(c['sword_thumb_fit_r45']))

if __name__=='__main__':main()
