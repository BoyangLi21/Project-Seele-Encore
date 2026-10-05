"""Fit finger pads to the real palm using measured skin endpoints and joint limits."""
from pathlib import Path
import json
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation as R
ROOT=Path(__file__).resolve().parents[1]/'artifacts/rebuild_r48'
result={}
def rz(angle):return R.from_rotvec([0,0,angle]).as_matrix()
for slot,name in [(3,'un00'),(4,'un01')]:
    folder=ROOT/'tripo_pipeline'/name/'rig_candidate';land=json.loads((folder/'rig_landmarks.json').read_text());skin=json.loads((folder/'smoothed_skin.json').read_text())
    v=np.load(folder.parent/'lod0_geometry.npz')['vertices'];ids=np.asarray(skin['skin_indices']).reshape(-1,4);weights=np.asarray(skin['skin_weights']).reshape(-1,4)
    seg={s['bone']:s for s in land['segments']};bones={b['name']:b for b in land['bones']};palette=skin['bones'];out={};evidence=[]
    for side,sign in [('r',-1),('l',1)]:
        out[side]={};wrist=np.array(bones['hand_'+side]['pivot'])
        for digit in ('index','middle','ring','little'):
            names=['finger_'+digit+(''if j==0 else '_tip'if j==1 else '_distal')+'_'+side for j in range(3)]
            p=[np.array(seg[n]['start'])for n in names];tip=np.array(seg[names[-1]]['end'])
            index=palette.index(names[-1]);selected=np.where(ids==index,weights,0).sum(1)>.45
            if selected.sum()>12:
                points=v[selected];along=(tip-p[-1]);along/=np.linalg.norm(along);projection=(points-p[-1])@along
                tip=points[projection>=np.quantile(projection,.95)].mean(0)
                seg[names[-1]]['end']=tip.tolist()
            p.append(tip);vectors=np.diff(np.array(p),axis=0)
            goal=np.array([wrist[0]+sign*.017,wrist[1]-.012,tip[2]])
            def endpoint(angles):
                total=0;point=p[0].copy()
                for angle,delta in zip(angles,vectors):total+=angle*sign;point+=rz(total)@delta
                return point
            a0=np.arctan2(vectors[0,1],vectors[0,0]*sign);a1=np.arctan2(vectors[1,1],vectors[1,0]*sign);a2=np.arctan2(vectors[2,1],vectors[2,0]*sign)
            neutral1=(a1-a0+np.pi)%(2*np.pi)-np.pi;neutral2=(a2-a1+np.pi)%(2*np.pi)-np.pi
            low=np.deg2rad([0,-15,-10]);high=np.array([np.deg2rad(140),max(np.deg2rad(15),np.deg2rad(110)-neutral1),max(np.deg2rad(20),np.deg2rad(95)-neutral2)])
            preference=np.minimum(np.deg2rad([85,40,35]),high-.001)
            def residual(a):return np.r_[(endpoint(a)-goal)*100,(a-preference)*.08]
            fit=least_squares(residual,preference,bounds=(low,high),max_nfev=120)
            out[side][digit]=(np.rad2deg(fit.x)*sign).tolist()
            evidence.append(dict(side=side,digit=digit,actual_tip=tip.tolist(),target=goal.tolist(),fitted_tip=endpoint(fit.x).tolist(),error_source_m=float(np.linalg.norm(endpoint(fit.x)-goal))))
    land['segments']=list(seg.values());(folder/'rig_landmarks.json').write_text(json.dumps(land,indent=2),'utf8')
    (folder/'fist_calibration.json').write_text(json.dumps(dict(angles=out,evidence=evidence),indent=2),'utf8');result[str(slot)]=out
    print(name,'fingertip target residual max',max(x['error_source_m']for x in evidence),flush=True)
target=ROOT/'un_native_candidate/assets/projectseele/motion/un_finger_poses_r48.json';target.parent.mkdir(parents=True,exist_ok=True)
target.write_text(json.dumps(dict(schema=48,fist=result),indent=2),'utf8')
