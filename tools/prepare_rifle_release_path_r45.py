"""Measure a support-hand opening path in the unchanged native weapon frame.

Exports full skinned surfaces, not fingertip proxies. No runtime asset is edited.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from eva_hand_rig_math_r45 import controls, matrices
from rebind_anatomical_hand_r45 import dq_pose


def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--witness',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();assert not a.out.exists();a.out.mkdir(parents=True)
    c=json.loads((a.candidate/'hand_rig_contract.json').read_text('utf8'))
    name=f"eva_unit0{c['rig']}";geo=json.loads((a.candidate/(name+'.geo.json')).read_text('utf8'))
    mesh=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text('utf8'))
    palettes={};parts={};static={}
    for line in a.witness.open(encoding='utf8'):
        r=json.loads(line)
        if r['kind']=='final_named_palette' and r['actual_owner_inputs']['weapon']==4 and r['stance']==0:palettes[r['tick']]=r
        elif r['kind']=='actual_static_part_geometry':static[r['resource_part']]=r
        elif r['kind']=='actual_cpu_submitted_part':parts.setdefault(r['tick'],{})[r['bone']]=r
    tick=next(t for t in reversed(palettes)if {'hand_l','cannon'}<=parts[t].keys())
    palette=palettes[tick];submitted=parts[tick]
    def actual(row):
        v=np.array(static[row['resource_part']]['original_part_xyz']).reshape(-1,3)
        changes=np.array(row['submitted_position_changes_index_xyz']).reshape(-1,4)
        v[changes[:,0].astype(int)]=changes[:,1:]
        v=(v+row['part_pivot_authored'])*[-1,1,1]/16
        m=np.array(row['mesh_to_world_column_major']).reshape(4,4).T
        points=v@m[:3,:3].T+m[:3,3]
        assert np.abs(points[row['actual_world_sample_vertex_indices']]-np.array(row['actual_world_sample_xyz']).reshape(-1,3)).max()<.01
        return points
    world=np.array(palette['model_to_world_column_major']).reshape(4,4).T
    bones={b['name']:np.array(b['final_model_column_major']).reshape(4,4).T for b in palette['bones']}
    neutral=matrices(geo,c,'l');transform=world@bones['hand_l']@np.linalg.inv(neutral['hand_l']);back=np.linalg.inv(transform)
    gun=actual(submitted['cannon']);weapon=gun@back[:3,:3].T+back[:3,3]
    gm=np.array(submitted['cannon']['mesh_to_world_column_major']).reshape(4,4).T
    gun_down=gm[:3,2]/np.linalg.norm(gm[:3,2]);down_per_metre=back[:3,:3]@gun_down
    part=mesh['parts']['hand_l'];skin=mesh['jointSkins']['hand_l']
    points=(np.array(part['vertices']).reshape(-1,8)[:,:3]+part['pivot'])*[-1,1,1]/16
    names=list(skin['influences']);weights=np.array([skin['influences'][n]for n in names]).T
    inv=[np.array(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in names]
    closed=controls(c,'rifle_left','l');opened=controls(c,'support','l')
    rows=[]
    for i,t in enumerate(np.linspace(0,1,41)):
        values={n:v*(1-t)+opened[n]*t for n,v in closed.items()}
        ms=matrices(geo,c,'l',values);posed=dq_pose(points,weights,[ms[n]@b for n,b in zip(names,inv)])
        if i==0:
            error=float(np.abs(posed@transform[:3,:3].T+transform[:3,3]-actual(submitted['hand_l'])).max())
            assert error<.002,('Closed-pose skin is not the actual draw',error)
        np.savez_compressed(a.out/f'open_{i:02d}.npz',hand=posed)
        rows.append(dict(index=i,opening=float(t)))
    np.savez_compressed(a.out/'geometry.npz',weapon=weapon,down_per_metre=down_per_metre)
    (a.out/'provenance.json').write_text(json.dumps(dict(candidate=str(a.candidate.resolve()),witness=str(a.witness.resolve()),
        witness_sha256=hashlib.sha256(a.witness.read_bytes()).hexdigest(),native_tick=tick,baseline_error_world=error,
        cases=rows,native_new_path_tested=False,visual_accepted=False),indent=2),'utf8')
    print('Exported 41 complete support-hand skins in the measured weapon frame; baseline error',error)


if __name__=='__main__':main()
