"""Freeze same controlled actor poses for original/new binding visual comparison."""
from pathlib import Path
import argparse,json,numpy as np
from replay_rigged_angel_witness_r44 import skin

ap=argparse.ArgumentParser();ap.add_argument('--witness',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--actor',required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
requested={'first_down':4190581,'shoulder_first_error':4190600,'recovery':4190662,'recovery_handoff':4190698,'second_down':4190779};selected={};identity=None
for line in args.witness.open(encoding='utf8'):
    row=json.loads(line)
    if row.get('kind')=='actual-parsed-weighted-resource':identity=row
    elif row.get('kind')=='actual-weighted-emit-vertices'and row['entity_uuid']==args.actor:
        for label,tick in requested.items():
            delta=abs(row['game_time']-tick)
            if label not in selected or delta<selected[label][0]:selected[label]=(delta,row)
assert identity is not None and len(selected)==len(requested);candidate=json.loads(args.candidate.read_text('utf8'));raw=np.asarray(identity['decoded_vertices'],np.float32).reshape(-1,8);assert np.array_equal(np.asarray(candidate['parts']['root']['vertices'],np.float32),raw.reshape(-1));assert candidate['skin']['bones']==identity['bones'];points=raw[:,:3].astype(float)*[-1/16,1/16,1/16];ids=np.asarray(candidate['skin']['indices']).reshape(-1,4);weights=np.asarray(candidate['skin']['weights']).reshape(-1,4);rows=[]
for label,(delta,row)in selected.items():
    palette=row['actual_palette'];matrices=np.asarray([b['actual_root_relative_matrix_column_major']for b in palette]).reshape(-1,4,4).transpose(0,2,1);real=np.asarray([b['actual_real_quaternion_xyzw']for b in palette])[:,[3,0,1,2]];dual=np.asarray([b['actual_dual_quaternion_xyzw']for b in palette])[:,[3,0,1,2]];scaled=np.asarray([b['scaled_lbs_branch']for b in palette]);world=np.asarray(row['actual_emit_to_world_matrix_column_major']).reshape(4,4).T;lift=np.asarray(row.get('actual_ground_support_translation_emit_xyz',[0,0,0]));new=skin(points,ids,weights,real,dual,matrices,scaled,'first-slot')[0];new_world=(new+lift)@world[:3,:3].T+world[:3,3];old_world=np.asarray(row['vertices_world_xyz']).reshape(-1,3)
    path=args.out/(label+'.npz');np.savez_compressed(path,old_world=old_world,new_world=new_world,world=world,uv=raw[:,3:5],neutral_emit=points,new_emit=new)
    row_info=dict(label=label,actor_uuid=args.actor,actual_game_time=row['game_time'],actual_frame=row['frame'],requested_tick=requested[label],tick_delta=delta,file=str(path.resolve()),original_first_error_edge_before_metres=float(np.linalg.norm(old_world[20796]-old_world[20797])),original_first_error_edge_after_metres=float(np.linalg.norm(new_world[20796]-new_world[20797])));rows.append(row_info)
(args.out/'actual_state_views.json').write_text(json.dumps(dict(rows=rows,candidate=str(args.candidate.resolve()),scope='Main controlled live-duel actor only. Original actual native world vertices versus fixed new weights on the same exact palette/world/ground shift. No replacement source pose or actual candidate-native execution.'),indent=2),'utf8');print(json.dumps(rows,indent=2))
