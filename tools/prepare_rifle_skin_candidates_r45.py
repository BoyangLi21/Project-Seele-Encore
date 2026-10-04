"""Measure finger-volume candidates in the actual native rifle/hand frame.

The unchanged weapon and reconstructed baseline must match recorded draw data.
This exports diagnostics only; it never installs or approves a hand pose.
"""
from pathlib import Path
import argparse, json, hashlib
import numpy as np
from eva_hand_rig_math_r45 import controls, matrices, contact_corrective
from rebind_anatomical_hand_r45 import dq_pose

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--witness',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--weapon',choices=('rifle','cannon'),default='rifle')
    ap.add_argument('--baseline-only',action='store_true')
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    c=json.loads((a.candidate/'hand_rig_contract.json').read_text('utf8'))
    name=f"eva_unit0{c['rig']}"
    geo=json.loads((a.candidate/(name+'.geo.json')).read_text('utf8'))
    mesh=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text('utf8'))
    palettes=[];parts={};static={}
    for line in a.witness.open(encoding='utf8'):
        row=json.loads(line)
        if row['kind']=='final_named_palette'and row['actual_owner_inputs']['weapon']==(4 if a.weapon=='rifle'else 2) and row['stance']==0:palettes.append(row)
        elif row['kind']=='actual_static_part_geometry':static[row['resource_part']]=row
        elif row['kind']=='actual_cpu_submitted_part':parts.setdefault(row['tick'],{})[row['bone']]=row
    palette=next(p for p in reversed(palettes)if all(n in parts[p['tick']]for n in ['cannon','hand_r','hand_l']))
    submitted=parts[palette['tick']]
    world=np.asarray(palette['model_to_world_column_major']).reshape(4,4).T
    bones={b['name']:np.asarray(b['final_model_column_major']).reshape(4,4).T for b in palette['bones']}
    def actual(row):
        v=np.asarray(static[row['resource_part']]['original_part_xyz']).reshape(-1,3).copy()
        changes=np.asarray(row['submitted_position_changes_index_xyz']).reshape(-1,4)
        v[changes[:,0].astype(int)]=changes[:,1:]
        v=(v+row['part_pivot_authored'])*[-1,1,1]/16
        m=np.asarray(row['mesh_to_world_column_major']).reshape(4,4).T
        points=v@m[:3,:3].T+m[:3,3]
        ids=row['actual_world_sample_vertex_indices']
        assert np.abs(points[ids]-np.asarray(row['actual_world_sample_xyz']).reshape(-1,3)).max()<.01
        return points
    gun=actual(submitted['cannon']);cases=[];receipts=[]
    for side,pose_name in [('r','rifle_right'),('l','rifle_left')]:
        cannon_pose='cannon_right' if side=='r' else 'cannon_left'
        if a.weapon=='cannon' and cannon_pose in c['pose_controls']:
            pose_name=cannon_pose
        hand='hand_'+side;part=mesh['parts'][hand];skin=mesh['jointSkins'][hand]
        points=(np.asarray(part['vertices']).reshape(-1,8)[:,:3]+part['pivot'])*[-1,1,1]/16
        names=list(skin['influences']);weights=np.asarray([skin['influences'][n]for n in names]).T
        inverse=[np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in names]
        neutral=matrices(geo,c,side);values=controls(c,pose_name,side)
        transform=world@bones[hand]@np.linalg.inv(neutral[hand]);back=np.linalg.inv(transform)
        weapon=gun@back[:3,:3].T+back[:3,3]
        def posed(v):
            ms=matrices(geo,c,side,v)
            result=dq_pose(points,weights,[ms[n]@iv for n,iv in zip(names,inverse)])
            return contact_corrective(geo,skin,result,ms,hand)
        baseline=posed(values);predicted=baseline@transform[:3,:3].T+transform[:3,3]
        error=float(np.abs(predicted-actual(submitted[hand])).max())
        assert error<.002,('Authoring skin does not reproduce native hand',side,error)
        digits=['thumb','index','middle','ring','little']
        mass=np.asarray([sum(weights[:,names.index(j['name'])]for j in c['hands'][side]['digits'][d]['joints'])for d in digits])
        labels=np.argmax(mass.reshape(5,-1,3).mean(2),axis=0)
        labels[mass.reshape(5,-1,3).mean(2).max(0)<.55]=-1
        faces=np.arange(len(points)).reshape(-1,3)
        np.savez_compressed(a.out/f'{side}_geometry.npz',weapon=weapon,faces=faces,labels=labels,baseline=baseline)
        if a.baseline_only:
            receipts.append(dict(side=side,pose=pose_name,native_tick=palette['tick'],baseline_native_error_world=error))
            continue
        for digit_index,digit in enumerate(digits):
            joints=c['hands'][side]['digits'][digit]['joints']
            tip=np.asarray(joints[-1]['tip_bind'])
            tip_ids=np.flatnonzero((mass[digit_index]>.7)&(np.linalg.norm(points-tip,axis=1)<.09))
            assert len(tip_ids)>3,(side,digit,'Missing actual fingertip patch')
            for factor in [.25,.375,.5,.625,.75,.875,1.,1.125]:
                current={n:v.copy()for n,v in values.items()}
                for joint in joints:
                    n=joint['name'];lo,hi=joint['anatomical_limits_degrees'][0]
                    current[n][0]=np.clip(values[n][0]*factor,lo,hi)
                label=f'{side}_{digit}_{factor:g}'
                vertices=posed(current)
                np.savez_compressed(a.out/(label+'.npz'),vertices=vertices,tip_ids=tip_ids)
                cases.append(dict(case=label,side=side,digit=digit,digit_index=digit_index,factor=factor,
                                  controls={j['name']:current[j['name']].tolist()for j in joints}))
        receipts.append(dict(side=side,native_tick=palette['tick'],baseline_native_error_world=error))
    (a.out/'cases.json').write_text(json.dumps(cases,indent=2),'utf8')
    (a.out/'provenance.json').write_text(json.dumps(dict(candidate=str(a.candidate.resolve()),witness=str(a.witness.resolve()),
        contract_sha256=hashlib.sha256((a.candidate/'hand_rig_contract.json').read_bytes()).hexdigest(),
        gun_sha256=submitted['cannon']['loaded_resource_sha256'],weapon=a.weapon,receipts=receipts,installed=False,visual_accepted=False),indent=2),'utf8')
    print('Prepared',len(cases),'native-frame finger-volume candidates',receipts,flush=True)

if __name__=='__main__':main()
