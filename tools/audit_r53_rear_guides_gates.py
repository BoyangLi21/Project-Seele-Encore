"""Read-only continuous gate/rail broadphase and convex swept-facet audit.

Each exported gate stage is a certified monotone translation. The convex hull
of each triangle's two endpoint positions is its exact swept set. Rail pieces
use their convex vertex enclosure, so a reported hit needs review; absence of
hits proves clearance for the complete gate motion, not only sampled poses.
"""
import argparse
import gzip
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from project_upright_gate_collisions_r52 import matrix


def read_profile(path):
    data=memoryview(gzip.decompress(path.read_bytes()));offset=4;parts=[]
    for _ in range(struct.unpack_from('>i',data,0)[0]):
        size=struct.unpack_from('>H',data,offset)[0];offset+=2
        name=bytes(data[offset:offset+size]).decode('utf8');offset+=size
        moving=bool(data[offset]);offset+=1
        size=struct.unpack_from('>i',data,offset)[0];offset+=4
        vertices=np.frombuffer(data[offset:offset+8*size],dtype='>f8').astype(float).reshape(-1,3,6)[:,:,:3];offset+=8*size
        parts.append((name,moving,vertices))
    assert offset==len(data)
    return parts


def transform(vertices,frame):
    return vertices@matrix(frame[3:]).T+frame[:3]


def convex_hit(a,b):
    # Barycentric feasibility also handles planar/degenerate swept triangles.
    # Translate close to zero to avoid numerical loss at deep world heights.
    centre=a.mean(0);a=a-centre;b=b-centre;n,m=len(a),len(b)
    equal=np.zeros((5,n+m));equal[:3,:n]=a.T;equal[:3,n:]=-b.T
    equal[3,:n]=1;equal[4,n:]=1
    result=linprog(np.zeros(n+m),A_eq=equal,b_eq=[0,0,0,1,1],bounds=(0,None),method='highs')
    if result.status not in (0,2):raise RuntimeError(result.message)
    return bool(result.success)


def audit(gates_path,rails_path,output):
    gates=json.loads(gates_path.read_text('utf8'));rails=json.loads(rails_path.read_text('utf8'))
    pieces=[]
    for part in rails['pieces']:
        v=np.unique(np.asarray(part['triangles_rgb']).reshape(-1,6)[:,:3],axis=0)+part['origin']
        pieces.append((part['name'],v))
    low=np.array([v.min(0) for _,v in pieces]);high=np.array([v.max(0) for _,v in pieces])
    cache={key:read_profile(gates_path.parent/p['mesh_file']) for key,p in gates['profiles'].items()}
    hits=[];tested=0
    for gate in gates['gates']:
        bounds=gate['complete_mesh_motion_broadphase_bounds']
        candidates=np.flatnonzero(np.all(high>=bounds[:3],axis=1)&np.all(low<=bounds[3:],axis=1))
        if not len(candidates):continue
        profile=gates['profiles'][gate['profile']];templates=cache[gate['profile']]
        count=0
        for sweep in profile['continuous_sweeps']:
            name,moving,tri=templates[sweep['part']]
            a=transform(transform(tri,sweep['from']),gate['world_root'])
            b=transform(transform(tri,sweep['to']),gate['world_root'])
            swept=np.concatenate([a,b],axis=1);lo=swept.min(1);hi=swept.max(1)
            for index in candidates:
                subset=np.flatnonzero(np.all(hi>=low[index],axis=1)&np.all(lo<=high[index],axis=1))
                if not len(subset):continue
                for triangle in subset:
                    tested+=1
                    if convex_hit(pieces[index][1],swept[triangle]):
                        hits.append(dict(gate=gate['resource'],part=name,moving=moving,
                            phase=[sweep['progress_from'],sweep['progress_to']],rail=pieces[index][0],
                            triangle=int(triangle),rail_bounds=[*low[index],*high[index]]))
                        count+=1;break
        print(gate['resource'],'rail candidates',len(candidates),'swept hits',count,flush=True)
    report=dict(schema='projectseele.r53.rear-guide-gate-audit.v1',world_written=False,
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (gates_path,rails_path)},
        gate_count=len(gates['gates']),rail_count=len(pieces),convex_tests=tested,
        collision_count=len(hits),collisions=hits,
        scope='Complete certified gate translations; convex enclosures of actual rail vertices')
    output.write_text(json.dumps(report,indent=2),'utf8')
    print('tested',tested,'hits',len(hits),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('gates','rails','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();audit(args.gates,args.rails,args.output)
