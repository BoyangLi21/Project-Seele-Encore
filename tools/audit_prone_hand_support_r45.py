"""Read real hand surfaces and palm orientation on the declared flat gait fixture."""
from pathlib import Path
import argparse,json
import numpy as np

p=argparse.ArgumentParser();p.add_argument('--native',type=Path,required=True)
p.add_argument('--candidate',type=Path,required=True);p.add_argument('--floor-y',type=float,required=True)
p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists()
c=json.loads((a.candidate/'hand_rig_contract.json').read_text('utf8'))
layers=json.loads(next((a.native/'native/native_media').rglob('body_layers_r40.json')).read_text('utf8'))
ticks={r['tick']:r['review_tick']for r in layers['samples']};static={};palette=None;rows=[]
for line in (a.native/'hand_vertices.jsonl').open(encoding='utf8'):
    r=json.loads(line)
    if r['kind']=='actual_static_part_geometry':static[r['resource_part']]=r
    elif r['kind']=='final_named_palette':palette=r
    elif r['kind']=='actual_cpu_submitted_part'and r['bone']in ['hand_l','hand_r']:
        assert palette is not None and palette['tick']==r['tick']
        step=ticks.get(r['tick']);
        if step is None or not(330<=step<=485):continue
        side=r['bone'][-1];bones={b['name']:b for b in palette['bones']}
        world=np.array(palette['model_to_world_column_major']).reshape(4,4).T
        hand=world@np.array(bones[r['bone']]['final_model_column_major']).reshape(4,4).T
        normal=hand[:3,:3]@np.array(c['hands'][side]['palmar_normal_bind']);normal/=np.linalg.norm(normal)
        along=hand[:3,:3]@np.array(c['hands'][side]['longitudinal_bind']);along/=np.linalg.norm(along)
        v=np.array(static[r['resource_part']]['original_part_xyz']).reshape(-1,3)
        edits=np.array(r['submitted_position_changes_index_xyz']).reshape(-1,4);v[edits[:,0].astype(int)]=edits[:,1:]
        v=(v+r['part_pivot_authored'])*[-1,1,1]/16
        transform=np.array(r['mesh_to_world_column_major']).reshape(4,4).T;v=v@transform[:3,:3].T+transform[:3,3]
        ids=r['actual_world_sample_vertex_indices'];error=float(np.abs(v[ids]-np.array(r['actual_world_sample_xyz']).reshape(-1,3)).max())
        assert error<.01
        rows.append(dict(tick=r['tick'],review_tick=step,side=side,stance=palette['stance'],
            hand_lowest_above_plane_m=float(v[:,1].min()-a.floor_y),palmar_normal_world=normal.tolist(),
            palm_down_alignment=float(-normal[1]),finger_longitudinal_up=float(along[1]),reconstruction_error_m=error))
assert rows
a.out.write_text(json.dumps(dict(scope='Actual submitted skin, bone-based central palm normal; specified native flat fixture floor, not a general terrain query',
    floor_y=a.floor_y,samples=rows,visual_accepted=False),indent=2),'utf8')
prone=[r for r in rows if r['stance']>=2.99]
print(json.dumps(dict(samples=len(rows),prone_samples=len(prone),
    palm_down_alignment_range=[min(r['palm_down_alignment']for r in prone),max(r['palm_down_alignment']for r in prone)],
    hand_plane_gap_range_m=[min(r['hand_lowest_above_plane_m']for r in prone),max(r['hand_lowest_above_plane_m']for r in prone)])))
