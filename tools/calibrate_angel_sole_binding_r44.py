"""Candidate-only plantar ownership repair; source user mesh is immutable.

The DCC negative demonstrates heel vertices split evenly between shin/foot.
An ankle blend belongs above the plantar surface, never on its floor patch.
Keep topology, UVs, bone indices, body vertices and every original file.
"""
from pathlib import Path
import argparse,copy,hashlib,json
import numpy as np

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/combat/tv_exchange'
RAW=ROOT/'artifacts/rebuild_r44/network_runtime/private_resources/assets/projectseele/mesh/sachiel.mesh.json'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=BASE/'counter_v3');args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    fixture=json.loads((BASE/'counter_v2/fixture.json').read_text('utf8'));data=next(a for a in fixture['actors']if a['key']=='sachiel');vertices=np.asarray(data['vertices']);weights=np.asarray(data['weights']);ids=np.asarray(data['influences']);names=[b['name']for b in data['bones']];changes=[]
    for side in('l','r'):
        foot=names.index('foot_'+side);shin=names.index('shin_'+side);foot_weight=np.where(ids==foot,weights,0).sum(1);shin_weight=np.where(ids==shin,weights,0).sum(1);ankle_z=data['joints']['leg_'+side]['end'][2]
        # The complete actual boot lies below this measured ankle band. Blend
        # only through the band above the ankle; the floor patch is rigid foot.
        z0=ankle_z+.2;z1=z0+2;eligible=(foot_weight>.045)&((foot_weight+shin_weight)>.8)&(vertices[:,2]<z1)
        blend=np.clip((z1-vertices[:,2])/(z1-z0),0,1);blend=blend*blend*(3-2*blend)
        for i in np.flatnonzero(eligible):
            old=weights[i].copy();current=old/max(1e-8,old.sum());new=current*(1-blend[i]);slot=int(np.flatnonzero(ids[i]==foot)[0]);new[slot]+=blend[i];weights[i]=new
            if np.max(np.abs(new-current))>.0001:changes.append(dict(vertex=int(i),side=side,neutral_z=float(vertices[i,2]),old=old.tolist(),new=new.tolist(),bone_slots=[names[j]for j in ids[i]]))
        mask=np.where(ids==foot,weights,0).sum(1)>.8;points=vertices[mask];front=points[points[:,1]>=np.percentile(points[:,1],85)];patch=front[front[:,2]<=front[:,2].min()+.35];pivot=np.asarray(data['joints']['leg_'+side]['end']);data['toes'][side].update(rest=patch.mean(0).tolist(),offset=(patch.mean(0)-pivot).tolist(),rest_floor=float(points[:,2].min()),vertices=points.tolist())
    data['weights']=weights.tolist();raw=json.loads(RAW.read_text('utf8'));skin=raw['skin'];skin_names=skin['bones'];source_weights=np.asarray(skin['weights']).reshape(-1,4);source_ids=np.asarray(skin['indices']).reshape(-1,4)
    if len(source_weights)!=len(weights):raise ValueError('Whole original skin/fixture vertex order differs')
    mapped=np.vectorize(lambda i:names.index(skin_names[i]))(source_ids)
    if not np.array_equal(mapped,ids):raise ValueError('Skin bone indices differ from original fixture')
    unchanged=source_weights.copy();skin['weights']=weights.reshape(-1).tolist();candidate=out/'sachiel_sole_bind_r44.mesh.json';candidate.write_text(json.dumps(raw,separators=(',',':')),'utf8')
    fixture['quality']='CANDIDATE ONLY: paired counter with plantar binding revision; no artistic/native acceptance.';data['skin_scope']='Private candidate: shin/foot plantar split corrected below measured ankle; above-ankle smooth blend and original topology/UVs/bones retained.'
    (out/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8')
    result=dict(source_file=str(RAW),source_sha256=hashlib.sha256(RAW.read_bytes()).hexdigest(),candidate=str(candidate),candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
        vertices_changed=len(changes),source_geometry_vertices=len(weights),source_file_written=False,method='Complete plantar ownership by foot; only the anatomical band above ankle retains smooth shin blending.',
        topology_uv_bone_indices_changed=False,scope='Private mesh/DCC comparison. Not installed into runtime; no game/artistic acceptance.',changes=changes)
    (out/'sole_binding_receipt.json').write_text(json.dumps(result,indent=2),'utf8');print(json.dumps({k:v for k,v in result.items()if k!='changes'},indent=2))


if __name__=='__main__':main()
