"""Absolute lengths and effective bone groups for shared native strain cases."""
from pathlib import Path
import argparse,json
import numpy as np
from replay_rigged_angel_witness_r44 import skin

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--witness',type=Path,required=True);ap.add_argument('--audit',type=Path,required=True);ap.add_argument('--binding',default='original');ap.add_argument('--candidate',type=Path);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    audit=json.loads(args.audit.read_text('utf8'));wanted={(value['summary'][args.binding]['dominant']['worst_frame'],actor)for actor,value in audit['summary_by_actor'].items()};rows=[];source=None;candidate=json.loads(args.candidate.read_text('utf8'))if args.candidate else None
    for line in args.witness.open(encoding='utf8'):
        row=json.loads(line)
        if row.get('kind')=='actual-parsed-weighted-resource':
            source=row;points=np.asarray(source['decoded_vertices'],np.float32).reshape(-1,8)[:,:3].astype(float)*[-1/16,1/16,1/16];ids=np.asarray(source['parsed_indices']).reshape(-1,4);weights=np.asarray(source['parsed_weights'],np.float32).reshape(-1,4).astype(float);names=source['bones']
            if candidate:
                assert names==candidate['skin']['bones'];assert np.array_equal(np.asarray(candidate['parts']['root']['vertices'],np.float32),np.asarray(source['decoded_vertices'],np.float32));ids=np.asarray(candidate['skin']['indices']).reshape(-1,4);weights=np.asarray(candidate['skin']['weights']).reshape(-1,4)
            continue
        if row.get('kind')!='actual-weighted-emit-vertices'or(row['frame'],row['entity_uuid'])not in wanted:continue
        palette=row['actual_palette'];real=np.asarray([b['actual_real_quaternion_xyzw']for b in palette])[:,[3,0,1,2]];dual=np.asarray([b['actual_dual_quaternion_xyzw']for b in palette])[:,[3,0,1,2]];matrices=np.asarray([b['actual_root_relative_matrix_column_major']for b in palette]).reshape(-1,4,4).transpose(0,2,1);scaled=np.asarray([b['scaled_lbs_branch']for b in palette]);world=np.asarray(row['actual_emit_to_world_matrix_column_major']).reshape(4,4).T;lift=np.asarray(row.get('actual_ground_support_translation_emit_xyz',[0,0,0]));posed=skin(points,ids,weights,real,dual,matrices,scaled,'dominant')[0];actual=np.asarray(row['vertices_world_xyz']).reshape(-1,3);neutral=points@world[:3,:3].T;canonical=posed@world[:3,:3].T+world[:3,3]+lift@world[:3,:3].T
        original_triangle=points.reshape(-1,3,3);neutral_triangle=neutral.reshape(-1,3,3);posed_triangle=canonical.reshape(-1,3,3);indices=np.arange(len(points)).reshape(-1,3);edges=[];affected=set();bones={}
        for k in range(3):
            a=indices[:,k];b=indices[:,(k+1)%3];base=np.linalg.norm(points[b]-points[a],axis=1);rest_world=np.linalg.norm(neutral[b]-neutral[a],axis=1);length=np.linalg.norm(canonical[b]-canonical[a],axis=1);ratio=np.divide(length,rest_world,out=np.zeros_like(length),where=rest_world>0);eligible=(base>.05)&(ratio>4)
            for face in np.flatnonzero(eligible):
                u=int(a[face]);v=int(b[face]);affected.add(int(face));ownership={names[int(i)]for vertex in(u,v)for i,w in zip(ids[vertex],weights[vertex])if w>.01};key=','.join(sorted(ownership));bones[key]=bones.get(key,0)+1
                edges.append(dict(face=int(face),vertices=[u,v],static_world_length_metres=float(rest_world[face]),posed_world_length_metres=float(length[face]),ratio=float(ratio[face]),actual_native_world_length_metres=float(np.linalg.norm(actual[v]-actual[u])),endpoints=[dict(vertex=vertex,neutral_emit=points[vertex].tolist(),dominant_world=canonical[vertex].tolist(),actual_native_world=actual[vertex].tolist(),influences=[dict(bone=names[int(i)],weight=float(w))for i,w in zip(ids[vertex],weights[vertex])if w>0])for vertex in(u,v)]))
        result=dict(actor_uuid=row['entity_uuid'],frame=row['frame'],world_tick=row['game_time'],binding=args.binding,policy='stable dominant reference, fixed effective weights for named binding; actual_native fields retain original baseline weights',affected_nontrivial_triangles_over_four_times=len(affected),affected_edge_bone_groups=bones,worst_ratio_edges=sorted(edges,key=lambda e:e['ratio'],reverse=True)[:20],longest_absolute_edges=sorted(edges,key=lambda e:e['posed_world_length_metres'],reverse=True)[:20]);rows.append(result)
        np.savez_compressed(args.out/('strain_'+row['entity_uuid']+'.npz'),neutral_points_emit=points,dominant_emit=posed,actual_native_emit=np.asarray(row['vertices_emit_xyz']).reshape(-1,3),world=world,lift=lift,ids=ids,weights=weights)
        (args.out/('actual_palette_'+row['entity_uuid']+'.json')).write_text(json.dumps(row),'utf8')
    assert len(rows)==len(wanted);(args.out/'absolute_native_strain_readback.json').write_text(json.dumps(dict(rows=rows,scope='World-space lengths from actual same-frame renderer transform and fixed original weights. Threshold excludes neutral edges below .05 emit units (~.25m for scale5). Bone groups, face counts and native actual length are explicit; ratio alone is not artistic acceptance.'),indent=2),'utf8')
    for row in rows:print(json.dumps(dict(actor=row['actor_uuid'],tick=row['world_tick'],faces=row['affected_nontrivial_triangles_over_four_times'],worst=row['worst_ratio_edges'][0]),indent=2))

if __name__=='__main__':main()
