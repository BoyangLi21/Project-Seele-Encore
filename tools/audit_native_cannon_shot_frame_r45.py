"""Compare recorded shots with preceding actual submitted cannon geometry.

Samples are labelled with their tick separation; this is not a same-render
event proof or a declaration that the living-target test passed.
"""
from pathlib import Path
import argparse,json
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--witness',type=Path,required=True)
p.add_argument('--result',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
rows=[json.loads(s)for s in a.witness.open(encoding='utf8')]
palettes={r['tick']:r for r in rows if r['kind']=='final_named_palette'}
parts={r['tick']:r for r in rows if r['kind']=='actual_cpu_submitted_part'and r['bone']=='cannon'}
result=json.loads(a.result.read_text('utf8'));shots=result['stance_r41']['server_actual_shots'];proof=[];selected=set()
for shot in shots:
    prior=[t for t in parts if t in palettes and 0<=shot['server_tick']-t<=30 and abs(palettes[t]['stance']-shot['stance'])<.01]
    assert prior,'No bounded preceding native cannon sample for shot'
    tick=max(prior);part=parts[tick];m=np.asarray(part['mesh_to_world_column_major']).reshape(4,4).T
    tip=(np.array([.311045,-90.93669,-3.629085])+part['part_pivot_authored'])*[-1,1,1]/16
    tip=(m@np.r_[tip,1])[:3];direction=-m[:3,1];direction/=np.linalg.norm(direction)
    ray=np.asarray(shot['server_actual_direction']);ray/=np.linalg.norm(ray)
    proof.append(dict(case=shot['case'],stance=shot['stance'],pitch=shot['weapon_pitch'],
        actual_native_tick=tick,server_shot_tick=shot['server_tick'],sample_gap_ticks=shot['server_tick']-tick,
        actual_mesh_sha256=part['loaded_resource_sha256'],
        angular_error_degrees=float(np.degrees(np.arccos(np.clip(direction@ray,-1,1)))),
        native_cap_to_later_server_ray_blocks=float(np.linalg.norm(tip-shot['server_actual_muzzle'])),
        actual_native_cap=tip.tolist(),actual_native_axis=direction.tolist()))
    selected.add(tick)
(a.out/'shot_frame_measurements.json').write_text(json.dumps(dict(actual_shots=len(shots),
    complete_native_test_passed=result['passed'],same_render_shot_capture=False,user_art_accepted=False,measurements=proof),indent=2),'utf8')
(a.out/'witness.jsonl').write_text(''.join(json.dumps(r)+'\n'for r in rows if r['kind']=='actual_static_part_geometry'or r.get('tick')in selected),'utf8')
print(json.dumps(proof,indent=2))
