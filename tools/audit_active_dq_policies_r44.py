"""Separate fixed binding, blend policy, hemisphere and continuity on real draws.

No weights, skeleton, renderer or source palettes are changed. Agreement
between different blend policies is not an acceptance condition.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from replay_rigged_angel_witness_r44 import skin

def measures(points,posed):
    triangles=points.reshape(-1,3,3);actual=posed.reshape(-1,3,3);base=np.concatenate([triangles[:,(k+1)%3]-triangles[:,k]for k in range(3)]);now=np.concatenate([actual[:,(k+1)%3]-actual[:,k]for k in range(3)]);length=np.linalg.norm(base,axis=1);use=length>.05;ratio=np.linalg.norm(now,axis=1)[use]/length[use]
    return dict(nontrivial_edges=int(use.sum()),maximum_edge_stretch_ratio=float(ratio.max()),edges_over_four_times=int((ratio>4).sum()),edges_over_ten_times=int((ratio>10).sum()))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--witness',type=Path,required=True);ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--candidate-label',default='C6');ap.add_argument('--allow-added-geometry',action='store_true');ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    candidate=json.loads(args.candidate.read_text('utf8'));source=None;rows=[];previous={};selected={};focus=(20309,29633,30590,13073);policies=('first-slot','dominant','running-sum','running-weight-descending')
    for line in args.witness.open(encoding='utf8'):
        row=json.loads(line);kind=row.get('kind')
        if kind=='actual-parsed-weighted-resource':
            source=row;raw=np.asarray(row['decoded_vertices'],np.float32).reshape(-1,8);points=raw[:,:3].astype(float)*[-1/16,1/16,1/16];source_ids=np.asarray(row['parsed_indices']).reshape(-1,4);source_weights=np.asarray(row['parsed_weights'],np.float32).reshape(-1,4).astype(float);ids=np.asarray(candidate['skin']['indices']).reshape(-1,4);weights=np.asarray(candidate['skin']['weights']).reshape(-1,4)
            assert candidate['skin']['bones']==row['bones'];candidate_raw=np.asarray(candidate['parts']['root']['vertices'],np.float32).reshape(-1,8);assert np.array_equal(candidate_raw[:len(raw)],raw);assert args.allow_added_geometry or len(candidate_raw)==len(raw);candidate_points=candidate_raw[:,:3].astype(float)*[-1/16,1/16,1/16];continue
        if kind!='actual-weighted-emit-vertices'or row['branch']=='wrap-cache':continue
        assert source is not None;palette=row['actual_palette'];names=[p['bone']for p in palette];assert names==source['bones'];real=np.asarray([p['actual_real_quaternion_xyzw']for p in palette])[:,[3,0,1,2]];dual=np.asarray([p['actual_dual_quaternion_xyzw']for p in palette])[:,[3,0,1,2]];matrices=np.asarray([p['actual_root_relative_matrix_column_major']for p in palette]).reshape(-1,4,4).transpose(0,2,1);scaled=np.asarray([p['scaled_lbs_branch']for p in palette]);world=np.asarray(row['actual_emit_to_world_matrix_column_major']).reshape(4,4).T;lift=np.asarray(row.get('actual_ground_support_translation_emit_xyz',[0,0,0]));actual=np.asarray(row['vertices_emit_xyz']).reshape(-1,3);per_binding={}
        for binding,bp,bi,bw in(('original',points,source_ids,source_weights),(args.candidate_label,candidate_points,ids,weights)):
            predictions={};norms={};report={}
            order=np.lexsort((bi,-bw),axis=1);sorted_ids=np.take_along_axis(bi,order,1);sorted_weights=np.take_along_axis(bw,order,1)
            for policy in policies:
                local,norm,lbs=skin(bp,sorted_ids if policy=='running-weight-descending'else bi,sorted_weights if policy=='running-weight-descending'else bw,real,dual,matrices,scaled,'running-sum'if policy=='running-weight-descending'else policy);predictions[policy]=local;norms[policy]=norm;report[policy]=dict(minimum_blended_real_norm=float(norm.min()),scaled_lbs_vertices=int(lbs.sum()),**measures(bp,local))
            native_error=np.linalg.norm(predictions['first-slot'][:len(actual)]+lift-actual,axis=1);differences={}
            for policy in policies[1:]:
                distance=np.linalg.norm(predictions['first-slot']-predictions[policy],axis=1);v=int(distance.argmax());differences[policy]=dict(maximum_emit_distance=float(distance[v]),worst_vertex=v)
            key=(row['entity_uuid'],binding);continuity={}
            if key in previous:
                for policy in policies:
                    delta=np.linalg.norm(predictions[policy]-previous[key][policy],axis=1);continuity[policy]=dict(maximum_local_vertex_motion_emit=float(delta.max()),worst_vertex=int(delta.argmax()),scope='Contains actual physical bone motion; no discontinuity verdict from this scalar alone')
            previous[key]=predictions
            focus_rows=[]
            for vertex in focus:
                positive=[int(i)for i,w in zip(bi[vertex],bw[vertex])if w>0];qw=real[positive];dots=qw@qw.T
                dominant=min((int(i)for i,w in zip(bi[vertex],bw[vertex])if w==bw[vertex].max()))
                signs=np.where(real[bi[vertex]]@real[bi[vertex,0]]<0,-1,1);strong=np.flatnonzero(bw[vertex]>.1)
                focus_rows.append(dict(vertex=vertex,effective_influences=[dict(bone=names[int(i)],weight=float(w))for i,w in zip(bi[vertex],bw[vertex])if w>0],physical_relative_rotation_degrees=(np.degrees(2*np.arccos(np.clip(np.abs(dots),0,1)))).tolist(),stored_first_reference=names[int(bi[vertex,0])],dominant_reference=names[dominant],stored_first_signs=signs.tolist(),strong_pair_reference_forces_opposite_signs=bool(len(strong)>=2 and signs[strong[0]]!=signs[strong[1]]),policy_positions_emit={p:predictions[p][vertex].tolist()for p in policies}))
            per_binding[binding]=dict(native_first_slot_replay_error_emit=float(native_error.max())if binding=='original'else None,policies=report,policy_separation=differences,continuity=continuity,focus=focus_rows)
            if binding=='original':
                score=differences['dominant']['maximum_emit_distance']
                if 'original'not in selected or score>selected['original']['score']:
                    selected['original']=dict(score=score,game_time=row['game_time'],frame=row['frame'],entity_uuid=row['entity_uuid']);np.savez_compressed(args.out/'largest_original_policy_separation.npz',neutral_points_emit=points,world=world,actual_lift_emit=lift,actual_native_emit=actual,**{p.replace('-','_'):v for p,v in predictions.items()});(args.out/'largest_original_palette.json').write_text(json.dumps(row),'utf8')
        rows.append(dict(game_time=row['game_time'],frame=row['frame'],entity_uuid=row['entity_uuid'],bindings=per_binding))
    assert rows;summary={}
    for binding in('original',args.candidate_label):
        summary[binding]={p:dict(maximum_edge_stretch_ratio=max(r['bindings'][binding]['policies'][p]['maximum_edge_stretch_ratio']for r in rows),maximum_edges_over_four_times=max(r['bindings'][binding]['policies'][p]['edges_over_four_times']for r in rows),minimum_blended_real_norm=min(r['bindings'][binding]['policies'][p]['minimum_blended_real_norm']for r in rows))for p in policies}
    grouped={}
    for actor in sorted(set(r['entity_uuid']for r in rows)):
        actor_rows=[r for r in rows if r['entity_uuid']==actor];actor_summary={}
        for binding in('original',args.candidate_label):
            actor_summary[binding]={}
            for policy in policies:
                worst=max(actor_rows,key=lambda r:r['bindings'][binding]['policies'][policy]['maximum_edge_stretch_ratio']);actor_summary[binding][policy]=dict(maximum_edge_stretch_ratio=worst['bindings'][binding]['policies'][policy]['maximum_edge_stretch_ratio'],worst_frame=worst['frame'],worst_world_tick=worst['game_time'],minimum_blended_real_norm=min(r['bindings'][binding]['policies'][policy]['minimum_blended_real_norm']for r in actor_rows),maximum_edges_over_four_times=max(r['bindings'][binding]['policies'][policy]['edges_over_four_times']for r in actor_rows))
        grouped[actor]=dict(samples=len(actor_rows),world_tick_range=[min(r['game_time']for r in actor_rows),max(r['game_time']for r in actor_rows)],summary=actor_summary)
    result=dict(actual_samples=len(rows),source_witness_sha256=hashlib.sha256(args.witness.read_bytes()).hexdigest(),candidate_sha256=hashlib.sha256(args.candidate.read_bytes()).hexdigest(),source_resource_sha256=source['source_bytes_sha256'],candidate_label=args.candidate_label,policies=policies,summary=summary,summary_by_actor=grouped,selected=selected,rows=rows,scope='Fixed original and named candidate effective weights across all actual native palettes. Stored first-slot, stable dominant reference, decoded running order and canonical weight-descending running are distinct algorithms. Actor groups must remain separate. Policy separation is not binding failure; triangle strain and continuity are diagnostics requiring actual artist review.',weights_modified_during_replay=False,original_geometry_prefix_retained=True,original_vertices=len(points),candidate_vertices=len(candidate_points),added_geometry_review_enabled=args.allow_added_geometry,renderer_modified=False,artistic_acceptance=False)
    (args.out/'active_fixed_weight_dq_policy_audit.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps(dict(samples=len(rows),summary=summary,selected=selected),indent=2))

if __name__=='__main__':main()
