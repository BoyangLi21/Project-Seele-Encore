"""Separate final palette, draw transform and CPU seam skin on actual native hands."""
from pathlib import Path
import json,numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat/runtime_hands_basis/native_v1_stream_readback';rows=[]
for tick in (4086952,4087483):
    palette=json.loads((OUT/f'v1_tick{tick}_palette.json').read_text('utf8'));world=np.asarray(palette['model_to_world_column_major']).reshape(4,4).T;bones={b['name']:b for b in palette['bones']}
    for file in OUT.glob(f'v1_tick{tick}_*_submitted.json'):
        row=json.loads(file.read_text('utf8'));name=row['bone'];before=np.asarray(row['original_part_xyz']).reshape(-1,3);after=np.asarray(row['submitted_part_xyz']).reshape(-1,3);draw=np.asarray(row['mesh_to_world_column_major']).reshape(4,4).T
        local_delta=(after-before)*[-1,1,1]/16;linear_world_delta=local_delta@draw[:3,:3].T;error=np.linalg.norm(linear_world_delta,axis=1)
        raw=(before+row['part_pivot_authored'])*[-1,1,1]/16;rigid=np.c_[raw,np.ones(len(raw))]@draw.T;actual=np.asarray(row['submitted_world_xyz']).reshape(-1,3)
        expected_draw=world@np.asarray(bones[name]['final_model_column_major']).reshape(4,4).T
        rows.append(dict(tick=tick,stance=palette['stance'],bone=name,vertices=len(before),CPU_skin_maximum_world_displacement=float(error.max()),
                         minimum_world_y_before_cpu_skin=float(rigid[:,1].min()),minimum_world_y_actual_submitted=float(actual[:,1].min()),
                         draw_vs_final_palette_rotation_max_component=float(np.abs(draw[:3,:3]-expected_draw[:3,:3]).max()),
                         draw_vs_final_palette_translation_max_component=float(np.abs(draw[:3,3]-expected_draw[:3,3]).max())))
(OUT/'actual_skin_stage_unit01.json').write_text(json.dumps(dict(rows=rows,scope='Same actual native frame, decoded original/CPU-submitted positions and actual draw matrix. CPU delta uses linear transform before large world translation, avoiding world-ULP confusion. Float64 product versus recorded JOML float32 final draw differences are recorded, not threshold-PASS claims.'),indent=2),'utf8')
print(json.dumps([dict(tick=tick,max_CPU_delta=max(r['CPU_skin_maximum_world_displacement']for r in rows if r['tick']==tick),max_draw_rotation=max(r['draw_vs_final_palette_rotation_max_component']for r in rows if r['tick']==tick),max_draw_translation=max(r['draw_vs_final_palette_translation_max_component']for r in rows if r['tick']==tick))for tick in (4086952,4087483)]))
