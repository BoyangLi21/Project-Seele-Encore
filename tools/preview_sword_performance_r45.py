"""Export the actual Unit02 sword grip on a full captured body, without game writes."""
from pathlib import Path
import argparse,json
import numpy as np
from author_combat_r35 import Actor
from study_combat_performance_r36 import decode
from eva_hand_rig_math_r45 import matrices,controls,contact_corrective
from rebind_anatomical_hand_r45 import dq_pose

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--profiles',type=Path,required=True);ap.add_argument('--hand',type=Path,required=True);ap.add_argument('--clip',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    a.out.mkdir(exist_ok=False,parents=True);actor=Actor(2);d=json.loads((a.profiles/'eva_gameplay_r42_2.json').read_text());clip=d['clips']['r32_'+a.clip]
    model=json.loads((ROOT/'run/resourcepacks/eva_real_model/assets/projectseele/mesh/eva_unit02.mesh.json').read_text())
    c=json.loads((a.hand/'hand_rig_contract.json').read_text());g=json.loads((a.hand/'eva_unit02.geo.json').read_text());hm=json.loads((a.hand/'eva_unit02_anatomical_hands_r45.mesh.json').read_text());grip=np.load(a.hand/'sword_grip_preview.npz')
    prepared={}
    for side in ['l','r']:
        bone='hand_'+side;part=hm['parts'][bone];skin=hm['jointSkins'][bone];raw=np.asarray(part['vertices']).reshape(-1,8);points=(raw[:,:3]+part['pivot'])*[-1,1,1]/16
        ms=matrices(g,c,side,controls(c,'sword_right'if side=='r'else'relaxed',side));palette=list(skin['influences']);weights=np.array([skin['influences'][n]for n in palette]).T
        transforms=[ms[n]@np.array(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette]
        posed=contact_corrective(g,skin,dq_pose(points,weights,transforms),ms,bone)
        prepared[side]=(posed,raw[:,3:5],np.linalg.inv(ms[bone]))
    manifest=[]
    for i,t in enumerate([0,.18,.38,.58,.78,1]):
        p=decode(actor,d,clip['frames'][round(t*(len(clip['frames'])-1))]);v=[];uv=[]
        for n,part in model['parts'].items():
            if n not in p.q or n.startswith(('hand_','finger_'))or n in ('knife','lance','shield'):continue
            raw=np.asarray(part['vertices']).reshape(-1,8);pts=(raw[:,:3]+part['pivot'])*[-1,1,1]
            v.append((np.c_[pts,np.ones(len(pts))]@p.matrix(n).T)[:,:3]);uv.append(raw[:,3:5])
        for side in ['l','r']:
            posed,tex,inverse=prepared[side];m=p.matrix('hand_'+side).copy();m[:3,3]/=16;m=m@inverse
            v.append((np.c_[posed,np.ones(len(posed))]@m.T)[:,:3]*16);uv.append(tex)
        weapon=grip['sword'];m=p.matrix('hand_r').copy();m[:3,3]/=16;m=m@prepared['r'][2]
        weapon=(np.c_[weapon,np.ones(len(weapon))]@m.T)[:,:3]*5
        name=f'eva_unit02_{i}';np.savez_compressed(a.out/(name+'.npz'),vertices=np.concatenate(v)*5/16,uv=np.concatenate(uv),weapon_vertices=weapon)
        manifest.append(dict(file=name,model='eva_unit02',phase=t,camera_target=[0,0,25],scale=88,camera_offset=[-85,125,30]))
    (a.out/'manifest.json').write_text(json.dumps(manifest))
if __name__=='__main__':main()
