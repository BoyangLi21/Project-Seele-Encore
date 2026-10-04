"""Contact-aware finger closure order around the admitted handle."""
from pathlib import Path
import argparse,json
import numpy as np
from eva_hand_rig_math_r45 import controls,matrices
from rebind_anatomical_hand_r45 import dq_pose


def ease(t):
    t=np.clip(t,0,1)
    return t*t*t*(10+t*(-15+6*t))


def equipment_controls(c,side,phase):
    first=controls(c,'knife_approach'if'knife_approach'in c['pose_controls']else'open',side);last=controls(c,'knife',side);values={}
    t=np.clip((phase-.42)/.12,0,1)
    for digit,d in c['hands'][side]['digits'].items():
        for i,j in enumerate(d['joints']):
            n=j['name']
            if digit=='thumb':u=ease((phase-.16)/.20)
            elif digit.startswith('cup_')or i==0:u=ease(t/.5)
            else:u=ease((t-(.35 if i==1 else .45))/(.65 if i==1 else .55))
            values[n]=first[n]*(1-u)+last[n]*u
    return values


def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    c=json.loads((a.candidate/'hand_rig_contract.json').read_text());name=f"eva_unit0{c['rig']}";g=json.loads((a.candidate/(name+'.geo.json')).read_text());m=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text())
    part=m['parts']['hand_r'];raw=np.array(part['vertices']).reshape(-1,8);points=(raw[:,:3]+part['pivot'])*[-1,1,1]/16;skin=m['jointSkins']['hand_r'];palette=list(skin['influences']);weights=np.array([skin['influences'][n]for n in palette]).T;inverses=[np.array(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette]
    first=controls(c,'open','r');last=controls(c,'knife','r');frames=[];records=[]
    # Opposition is established while the hand is still approaching the
    # shoulder. An abducted thumb sweeping through an already seated handle
    # cannot be repaired by changing the final closed pose.
    for j in c['hands']['r']['digits']['thumb']['joints']:first[j['name']]=last[j['name']].copy()
    for t in np.linspace(0,1,25):
        values={}
        for digit,d in c['hands']['r']['digits'].items():
            for i,j in enumerate(d['joints']):
                n=j['name']
                if digit.startswith('cup_'):u=ease(t/.5)
                elif digit=='thumb':u=ease(t/.5)if i==0 else ease((t-.5)/.5)
                else:u=ease(t/.5)if i==0 else ease((t-(.35 if i==1 else .45))/(.65 if i==1 else .55))
                values[n]=first[n]*(1-u)+last[n]*u
        ms=matrices(g,c,'r',values);frames.append(dq_pose(points,weights,[ms[n]@iv for n,iv in zip(palette,inverses)]));records.append(dict(phase=float(t),controls={n:v.tolist()for n,v in values.items()}))
    np.savez_compressed(a.out/'surfaces.npz',hands=np.asarray(frames),knife=np.load(a.candidate/'knife_preview.npz')['knife'])
    (a.out/'controls.json').write_text(json.dumps(records,indent=2),encoding='utf8')


if __name__=='__main__':main()
