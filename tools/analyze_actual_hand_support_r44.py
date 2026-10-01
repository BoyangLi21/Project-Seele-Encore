"""Actual final hand normal and full submitted surface clearance at selected native ticks."""
from pathlib import Path
import json,numpy as np
from scipy.spatial.transform import Rotation as R
from prepare_tv_exchange_r44 import raw_rig
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat/runtime_hands_basis/native_v1_stream_readback'
doc=json.loads((OUT/'native_hand_stage_readback.json').read_text('utf8'));assets=('eva_unit00','eva_unit01','eva_unit02','eva_prototype','eva_un01');rows=[]
for target in doc['target_client_rows']:
    v=target['variant'];possible=[r for r in doc['selected_actual_records']if r['variant']==v and r['kind']=='final_named_palette'];selected=min(possible,key=lambda r:abs(r['tick']-target['tick']));tick=selected['tick']
    palette=json.loads((OUT/selected['file']).read_text('utf8'));bones={b['name']:b for b in palette['bones']};world=np.asarray(palette['model_to_world_column_major']).reshape(4,4).T
    rig,p,neutral,path=raw_rig(assets[v])
    for side in ('l','r'):
        width=p['finger_index_'+side]-p['finger_little_'+side];width/=np.linalg.norm(width);along=p['hand_'+side]-p['forearm_'+side];along-=width*(along@width);along/=np.linalg.norm(along)
        normal=np.cross(width,along);normal/=np.linalg.norm(normal)
        bind=R.from_euler('xyz',np.asarray(rig['finger_middle_axis_'+side].get('rotation',[0,0,0]))*[-1,-1,1],degrees=True)
        if normal@bind.apply([1,0,0])<0:normal=-normal
        hand=np.asarray(bones['hand_'+side]['final_model_column_major']).reshape(4,4).T;actual=world[:3,:3]@hand[:3,:3]@normal;actual/=np.linalg.norm(actual)
        parts=[]
        for file in OUT.glob(f'v{v}_tick{tick}_*_submitted.json'):
            row=json.loads(file.read_text('utf8'))
            if not row['bone'].endswith('_'+side):continue
            points=np.asarray(row['submitted_world_xyz']).reshape(-1,3);before=np.asarray(row['original_part_xyz']).reshape(-1,3);after=np.asarray(row['submitted_part_xyz']).reshape(-1,3)
            parts.append(dict(bone=row['bone'],vertices=len(points),actual_minimum_world_y=float(points[:,1].min()),clearance_above_known_QA_floor_top_281=float(points[:,1].min()-281),
                              exact_CPU_position_change_vertices=int(np.any(before.astype(np.float32)!=after.astype(np.float32),axis=1).sum())))
        rows.append(dict(variant=v,side=side,requested_age=target['requested_age'],observed_client_age=target['observed_age'],actual_witness_tick=tick,stance=palette['stance'],shared_hands=palette['shared_hands'],
                         actual_R41_palmar_normal_world=actual.tolist(),angle_from_world_down_degrees=float(np.degrees(np.arccos(np.clip(-actual[1],-1,1)))),parts=parts))
(OUT/'actual_palm_support_stage.json').write_text(json.dumps(dict(rows=rows,scope='Actual native final named hand palette and every actual submitted hand/finger vertex in selected frame. Ground top281 belongs guarded QA floor only. Palmar axis is the R41 construction, not an independently measured flesh normal; normal mismatch locates a target/owner issue, not a visual pass.'),indent=2),'utf8')
print(json.dumps([dict(variant=r['variant'],side=r['side'],age=r['requested_age'],stance=r['stance'],down_angle=r['angle_from_world_down_degrees'],lowest=min(p['clearance_above_known_QA_floor_top_281']for p in r['parts']))for r in rows]))
