"""Freeze actual gun/shoulder/elbow frames for whole-arm grip authoring.

Undo only the measured hand contact adjustment. Check the unchanged native
weapon in the same authoring coordinates before exporting any guide.
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
from scipy.spatial.transform import Rotation


def main():
    p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    c=json.loads((a.candidate/'hand_rig_contract.json').read_text())
    report_file=next((a.native/'native/native').rglob('result.json'))
    report=json.loads(report_file.read_text());positions=report['stance_r41']['poses']
    actual_heights={float(p['position'][1])for p in positions}
    chosen=json.loads((a.native/'wrist_alignment.json').read_text())['selected']
    ticks={v['tick']:k for k,v in chosen.items()};frames={};parts={};static={}
    witness=a.native/'hand_vertices.jsonl'
    for line in witness.open():
        row=json.loads(line)
        if row['kind']=='final_named_palette' and row['tick']in ticks:frames[row['tick']]=row
        elif row['kind']=='actual_static_part_geometry':static[row['resource_part']]=row
        elif row['kind']=='actual_cpu_submitted_part'and row['tick']in ticks and row['bone']=='cannon':parts[row['tick']]=row
    guides=[]
    for tick,row in frames.items():
        world=np.array(row['model_to_world_column_major']).reshape(4,4).T
        bones={b['name']:b for b in row['bones']};gun=parts[tick]
        gm=np.array(gun['mesh_to_world_column_major']).reshape(4,4).T
        points=np.array(static[gun['resource_part']]['original_part_xyz']).reshape(-1,3).copy()
        changes=np.array(gun['submitted_position_changes_index_xyz']).reshape(-1,4)
        points[changes[:,0].astype(int)]=changes[:,1:]
        points=(points+gun['part_pivot_authored'])*[-1,1,1]/16
        gun_world=points@gm[:3,:3].T+gm[:3,3]
        right=gm[:3,0]/np.linalg.norm(gm[:3,0]);forward=-gm[:3,1]/np.linalg.norm(gm[:3,1])
        def matrix(name):return world@np.array(bones[name]['final_model_column_major']).reshape(4,4).T
        def point(name,pivot):return (matrix(name)@np.r_[pivot,1])[:3]
        for side in ('r','l'):
            frame=c['weapon_grip_frames'][side];fit=frame['pose_adjustment_r45'];palm=np.array(frame['palm_bind'])
            rotation=Rotation.from_quat(fit['rotation_xyzw']).as_matrix();adjustment=np.eye(4)
            adjustment[:3,:3]=rotation;adjustment[:3,3]=palm+fit['translation_native']-rotation@palm
            unadjusted=matrix('hand_'+side)@np.linalg.inv(adjustment);back=np.linalg.inv(unadjusted)
            measured=gun_world@back[:3,:3].T+back[:3,3]
            reference=np.load(a.input/f'{side}_geometry.npz')['weapon']
            error=float(np.abs(measured-reference).max());assert error<.002,('Different weapon/contact base',side,error)
            shoulder=point('arm_'+side,bones['arm_'+side]['pivot_model'])
            bind_wrist=np.array(bones['hand_'+side]['pivot_model']);wrist=point('hand_'+side,bind_wrist)
            elbow_pivot=bones.get('r30_elbow_socket_'+side,{}).get('pivot_model',np.array([-23.489652 if side=='l'else 23.489652,123.435069,7.737214])/16)
            elbow=point('forearm_'+side,elbow_pivot)
            high=np.clip((forward[1]-.35)/.35,0,1)
            pole=right*(1-.35*high if side=='r'else -1)+[0,-.7,0]
            if side=='l'and ticks[tick]=='crouch':
                # These selected settled samples occur after crawling stops.
                # Reproduce the actual kneeling pole rather than treating a
                # left supporting arm as the dominant arm's mirrored chain.
                socket=bones.get('r30_knee_socket_l')
                knee=np.asarray(socket['pivot_model'])if socket else np.asarray(bones['shin_l']['pivot_model'])+[0,11.4/16,0]
                knee=point('leg_l',knee);pole=knee-shoulder;pole/=np.linalg.norm(pole)
            guides.append(dict(stage=ticks[tick],side=side,tick=tick,stance=row['stance'],
                unadjusted_hand_to_world=unadjusted.tolist(),shoulder_world=shoulder.tolist(),
                wrist_bind=bind_wrist.tolist(),longitudinal_bind=c['hands'][side]['longitudinal_bind'],
                upper_length_world=float(np.linalg.norm(elbow-shoulder)),lower_length_world=float(np.linalg.norm(wrist-elbow)),
                preferred_pole_world=pole.tolist(),observed_elbow_world=elbow.tolist(),
                floor_elbow_height=float((row['actor_y']if 'actor_y'in row else next(iter(actual_heights))if len(actual_heights)==1 else float('nan'))+3.5),current_adjustment=fit,
                grounded_pole_weight=float(np.clip(row['stance']-2,0,1)),
                unchanged_weapon_frame_error_native=error,
                limitation='Settled stand/kneel/prone frames only. Actual elbow reproduction must pass before these can drive an authoring solve; transitions still need native review'))
    assert len(guides)==6 and not a.out.exists()
    assert all(np.isfinite(g['floor_elbow_height'])for g in guides),'Need actual actor height, not the renderer origin, for grounded elbow constraints'
    result=dict(source_witness=str(witness),source_sha256=hashlib.sha256(witness.read_bytes()).hexdigest(),
        contract_sha256=hashlib.sha256((a.candidate/'hand_rig_contract.json').read_bytes()).hexdigest(),
        original_solver_provenance=json.loads((a.input/'provenance.json').read_text()),guides=guides,
        actual_actor_height_source=dict(path=str(report_file),sha256=hashlib.sha256(report_file.read_bytes()).hexdigest(),pose_samples=len(positions),constant_heights=sorted(actual_heights)),
        native_new_pose_tested=False,visual_accepted=False)
    a.out.write_text(json.dumps(result,indent=2));print('Six measured whole-arm guides; weapon frame checked; no runtime edit')


if __name__=='__main__':main()
