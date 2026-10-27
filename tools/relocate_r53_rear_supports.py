"""Move only candidate support seats away from complete original gate sweeps.

Replacement seats are finite facets of the same already-generated rail. The
subsequent native-lining and exact swept-mesh audits remain mandatory.
"""
import argparse
import json
from pathlib import Path
import numpy as np


def relocate(source,gates,collisions,output):
    doc=json.loads(source.read_text('utf8'));gate=json.loads(gates.read_text('utf8'))
    failures=json.loads(collisions.read_text('utf8'))
    bad={int(v['rail'].split('/support/')[1].split('/')[0]) for v in failures['collisions']}
    bad|={v['index'] for v in doc.get('support_missing',[])}
    bounds=np.array([g['complete_mesh_motion_broadphase_bounds'] for g in gate['gates']
        if g['complete_mesh_motion_broadphase_bounds'][4]-g['complete_mesh_motion_broadphase_bounds'][1]<20])
    for index,socket in enumerate(doc['sockets']):
        point=np.asarray(socket['bearing'])
        if np.any(np.all(point>=bounds[:,:3]-1,axis=1)&np.all(point<=bounds[:,3:]+1,axis=1)):bad.add(index)
    candidates={}
    for p in doc['pieces']:
        if p['component']!='web':continue
        tri=np.asarray(p['triangles_rgb']).reshape(-1,3,6)[4,:,:3]+p['origin'];point=tri.mean(0)
        if np.any(np.all(point>=bounds[:,:3]-1,axis=1)&np.all(point<=bounds[:,3:]+1,axis=1)):continue
        normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);normal/=np.linalg.norm(normal)
        candidates.setdefault((p['leg'],p['mount']),[]).append((p['name'],tri,point,normal))
    moves=[]
    for index in sorted(bad):
        s=doc['sockets'][index];point=np.asarray(s['bearing'])
        p,tri,new,normal=min(candidates[(s['leg'],s['mount'])],key=lambda c:np.linalg.norm(c[2]-point))
        distance=float(np.linalg.norm(new-point))
        if distance>16:raise ValueError(('No bounded same-rail relocation',index,distance))
        moves.append(dict(socket=index,from_bearing=s['bearing'],to_bearing=new.tolist(),distance=distance))
        s['moved_from']={key:s[key] for key in ('rail_piece','weld_triangle','bearing','normal','metres')}
        s.update(rail_piece=p,weld_triangle=tri.tolist(),bearing=new.tolist(),normal=normal.tolist())
        s.pop('anchor',None)
    doc['pieces']=[p for p in doc['pieces'] if '/support/' not in p['name'] or int(p['name'].split('/support/')[1].split('/')[0]) not in bad]
    doc['support_relocations']=moves;doc['supports_complete']=False
    output.write_text(json.dumps(doc,separators=(',',':')),'utf8')
    print('relocated candidate seats',len(moves),'maximum movement',max(m['distance'] for m in moves),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('source','gates','collisions','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();relocate(args.source,args.gates,args.collisions,args.output)
