"""Locate first height change in actual same-render native pose layers."""
from pathlib import Path
import argparse,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,required=True);args=ap.parse_args();directory=args.directory
doc=json.loads((directory/'body_layers_r40.json').read_text('utf8'));body=json.loads((ROOT/'.Codex/r44-network-client/projectseele-local-maps/eva_body_r43.json').read_text('utf8'));rows=[]
actual_points={(v,'foot_'+s):np.load(ROOT/f'artifacts/rebuild_r44/combat/runtime_hands_basis/actual_foot_points/variant_{v}_foot_{s}.npy')for v in range(5)for s in ('l','r')}
clients=json.loads((directory/'client_samples.json').read_text('utf8'))
order=('source_clip','hands_before_initial_ground','initial_ground','authored','terrain','reaction','ground','feet','normalized','final')
for row in doc['samples']:
    variant=row['variant'];support=body.get('rig_support',{}).get(str(variant),body['support']);layers=[]
    for stage in order:
        if stage not in row['layers']:continue
        bones=row['layers'][stage];minimum={};actual={}
        for name in ('foot_l','foot_r','hand_l','hand_r','forearm_l','forearm_r','torso_lower','torso_upper'):
            if name not in bones or name not in support:continue
            points=np.asarray(support[name],float)/16;m=np.asarray(bones[name]['matrix']).reshape(4,4).T
            minimum[name]=float((points@m[1,:3]+m[1,3]).min()*5)
            if (variant,name)in actual_points:
                points=actual_points[(variant,name)];actual[name]=float((points@m[1,:3]+m[1,3]).min()*5)
        layers.append(dict(stage=stage,profile_support_minimum_relative_actor_y=minimum,
                           actual_original_foot_mesh_minimum_relative_actor_y=actual,
                           root_position_model_blocks=bones.get('root',{}).get('position_blocks')))
    differences=[]
    for before,after in zip(layers,layers[1:]):
        for bone,value in before['profile_support_minimum_relative_actor_y'].items():
            if bone in after['profile_support_minimum_relative_actor_y']:
                delta=after['profile_support_minimum_relative_actor_y'][bone]-value
                if abs(delta)>.02:differences.append(dict(before=before['stage'],after=after['stage'],bone=bone,height_delta_blocks=delta))
    nearby=[c for c in clients if c['variant']==variant and c['foot_witness']['support_r44']['game_time']==row['tick']]
    actual_draw=[]
    for c in nearby:
        witness=c['foot_witness'];actual_draw.append(dict(age=c['age'],l_minimum_y=witness.get('l_submitted_min_y'),r_minimum_y=witness.get('r_submitted_min_y'),actor_y=c['y']))
    rows.append(dict(variant=variant,entity_uuid=row['entity_uuid'],tick=row['tick'],stance=row['stance'],gait=row['gait'],layers=layers,height_changes=differences,actual_same_tick_foot_draw=actual_draw))
selected=[]
for v in range(5):
    for stance in (0.,1.,3.):
        choices=[r for r in rows if r['variant']==v and abs(r['stance']-stance)<.02]
        if choices:selected.append(choices[len(choices)//2])
report=dict(samples=len(rows),actual_same_render_layers=rows,selected_states=selected,
            scope='Actual captured native matrices, evaluated on the currently loaded body-profile support vertices. This isolates pose-stage height changes; support envelopes are not automatically identical to submitted mesh. FootWitness actual submitted minima provide the separate final-draw check. Art acceptance is not inferred.')
(directory/'body_layer_height_readback.json').write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps([dict(variant=r['variant'],stance=r['stance'],layers=r['layers'],height_changes=r['height_changes'])for r in selected if r['stance']>2.9],indent=2))
