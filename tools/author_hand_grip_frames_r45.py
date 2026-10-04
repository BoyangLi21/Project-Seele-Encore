"""Measure palm contacts on the actual new surface, not legacy finger pivots."""
from pathlib import Path
import argparse,json,shutil,hashlib
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
for f in a.candidate.iterdir():
 if f.is_file():shutil.copy2(f,a.out/f.name)
path=a.out/'hand_rig_contract.json';c=json.loads(path.read_text(encoding='utf8'));name=f"eva_unit0{c['rig']}";m=json.loads((a.out/(name+'_anatomical_hands_r45.mesh.json')).read_text(encoding='utf8'));frames={}
for side,h in c['hands'].items():
 part=m['parts']['hand_'+side];raw=np.asarray(part['vertices']).reshape(-1,8);points=(raw[:,:3]+part['pivot'])*[-1,1,1]/16;normal=raw[:,5:8]*[-1,1,1];n=np.asarray(h['palmar_normal_bind']);long=np.asarray(h['longitudinal_bind']);roots=np.asarray([h['digits'][d]['joints'][0]['head_bind']for d in ['index','middle','ring','little']]);hint=roots.mean(0)-long*.10+n*.055
 weights=np.asarray(m['jointSkins']['hand_'+side]['influences']['hand_'+side]);ids=np.flatnonzero((weights>.90)&((normal@n)>.5));assert len(ids)>20
 index=int(ids[np.argmin(np.linalg.norm(points[ids]-hint,axis=1))]);across=roots[0]-roots[-1];across-=long*(across@long);across/=np.linalg.norm(across)
 frames[side]=dict(palm_bind=points[index].tolist(),along_bind=long.tolist(),across_bind=across.tolist(),measured_vertex=index,palm_weight=float(weights[index]),basis='Actual dominant-palm vertex on the palm-facing surface, kept in model bind coordinates')
c['weapon_grip_frames']=frames
c['weapon_grip_source_r45']={name:hashlib.sha256((a.out/name).read_bytes()).hexdigest()for name in (name+'.geo.json',name+'_anatomical_hands_r45.mesh.json')}
path.write_text(json.dumps(c,indent=2),encoding='utf8');print(json.dumps(frames))
