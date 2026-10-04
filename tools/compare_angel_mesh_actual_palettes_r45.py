"""Replay unchanged native palettes with two explicit asset epochs, without pretending to render pixels."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np

def skin(points,ids,weights,q,d):
    Q=q[ids];D=d[ids];reference=Q[:,0:1,:]
    signed=weights*np.where(np.sum(reference*Q,axis=2)<0,-1,1)
    real=np.sum(Q*signed[:,:,None],axis=1);dual=np.sum(D*signed[:,:,None],axis=1)
    length=np.linalg.norm(real,axis=1);assert length.min()>1e-7
    real/=length[:,None];dual/=length[:,None];dual-=real*np.sum(real*dual,axis=1)[:,None]
    v=real[:,:3];w=real[:,3:];dv=dual[:,:3];dw=dual[:,3:]
    rotated=points+2*np.cross(v,np.cross(v,points)+w*points)
    translation=2*(-dw*v+w*dv-np.cross(dv,v))
    return rotated+translation

def main():
    p=argparse.ArgumentParser();p.add_argument('--witness',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    candidate=json.loads(a.candidate.read_text());assert candidate['parts']['root']['pivot']==[0,0,0]
    new=np.array(candidate['parts']['root']['vertices']).reshape(-1,8)[:,:3]*[-1/16,1/16,1/16]
    nids=np.array(candidate['skin']['indices']).reshape(-1,4);nw=np.array(candidate['skin']['weights']).reshape(-1,4)
    bind_tri=new.reshape(-1,3,3);bind_edges=bind_tri[:,[1,2,0]]-bind_tri
    rows=[];meta=None;worst=None
    for line in a.witness.open():
        r=json.loads(line)
        if r['kind']=='actual-parsed-weighted-resource':
            meta=r;old=np.array(r['decoded_vertices']).reshape(-1,8)[:,:3]*[-1/16,1/16,1/16];ids=np.array(r['parsed_indices']).reshape(-1,4);weights=np.array(r['parsed_weights']).reshape(-1,4)
        elif r['kind']=='actual-weighted-emit-vertices':
            assert meta and candidate['skin']['bones']==meta['bones']
            assert not any(x['scaled_lbs_branch'] for x in r['actual_palette']),'Separate exact LBS replay is required for scaled bones'
            pal={x['bone']:x for x in r['actual_palette']};q=np.array([pal[n]['actual_real_quaternion_xyzw']for n in meta['bones']]);d=np.array([pal[n]['actual_dual_quaternion_xyzw']for n in meta['bones']])
            before=skin(old,ids,weights,q,d);after=skin(new,nids,nw,q,d);observed=np.array(r['vertices_emit_xyz']).reshape(-1,3)
            error=float(np.abs(before-observed).max());assert error<.0001,error
            world=np.array(r['actual_emit_to_world_matrix_column_major']).reshape(4,4).T
            before=before@world[:3,:3].T+world[:3,3];after=after@world[:3,:3].T+world[:3,3]
            triangle=after.reshape(-1,3,3);rest_length=np.linalg.norm(bind_edges@world[:3,:3].T,axis=2);posed_length=np.linalg.norm(triangle[:,[1,2,0]]-triangle,axis=2)
            ratio=posed_length/np.maximum(rest_length,1e-12);valid=rest_length>=.05;severe=valid&(ratio>4)&(posed_length-rest_length>.5)
            rows.append(dict(game_time=r['game_time'],state=r['actual_sachiel_state'],before_min_y=float(before[:,1].min()),candidate_min_y=float(after[:,1].min()),baseline_emit_error=error,
                             candidate_severe_triangles=int(np.any(severe,axis=1).sum()),candidate_max_nontrivial_edge_ratio=float(np.where(valid,ratio,0).max())))
            if worst is None or rows[-1]['before_min_y']<worst:
                worst=rows[-1]['before_min_y'];np.savez_compressed(a.out/'worst_frame.npz',before=before,after=after,world=world);(a.out/'worst_palette.json').write_text(json.dumps(r['actual_palette']))
    result=dict(candidate=str(a.candidate),candidate_sha256=hashlib.sha256(a.candidate.read_bytes()).hexdigest(),native_current_sha256=meta['source_bytes_sha256'],rows=rows,scope='Actual old skin reconstruction checked; alternate mesh is offline palette replay, not native/art/user acceptance')
    (a.out/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(frames=len(rows),worst_old=min(x['before_min_y']for x in rows),worst_candidate=min(x['candidate_min_y']for x in rows))))

if __name__=='__main__':main()
