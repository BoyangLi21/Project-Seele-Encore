"""Measure candidate rear steel against frozen native collision shapes.

This is a diagnostic. Collisions, undeclared backing and moving door envelopes
remain unresolved until separately reviewed; no source or world is modified.
"""
import argparse
import collections
import itertools
import json
from pathlib import Path
import numpy as np
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry


def overlaps(triangles,lo,hi):
    """Triangle/AABB SAT, including coplanar and enclosed intersections."""
    centre=(lo+hi)/2;half=(hi-lo)/2-1e-6
    for tri in triangles-centre:
        edges=np.roll(tri,-1,axis=0)-tri
        axes=np.concatenate([np.eye(3),np.cross(edges[0],edges[1])[None],
            np.cross(edges[:,None,:],np.eye(3)[None,:,:]).reshape(-1,3)])
        axes=axes[np.einsum('ij,ij->i',axes,axes)>1e-20]
        extent=np.abs(axes)@half;proj=tri@axes.T
        if not np.any((proj.min(0)>=extent)|(proj.max(0)<=-extent)):return True
    return False


def audit(world,source,output):
    doc=json.loads(source.read_text('utf8'));m=MeasuredWorld(world);meshes=[]
    for p in doc['pieces']:
        vertices=np.asarray(p['triangles_rgb']).reshape(-1,3,6)[:,:,:3]+p['origin']
        lo=np.floor(vertices.min((0,1))).astype(int);hi=np.floor(vertices.max((0,1))).astype(int)
        m.box(tuple(lo),tuple(hi));meshes.append((p,vertices,lo,hi))
    # Measure backing near each declared socket, without designating arbitrary
    # solid or air as a new facility. Actual support selection is a later step.
    for s in doc['sockets']:
        p=np.floor(s['bearing']).astype(int);m.box(tuple(p-12),tuple(p+12))
    m.load();g=ActualGeometry(m);collisions=[];unknown=[];counts=collections.Counter()
    for part,tri,lo,hi in meshes:
        for cell in itertools.product(*(range(lo[i],hi[i]+1) for i in range(3))):
            shapes=g.boxes(cell)
            if shapes is None:unknown.append(dict(part=part['name'],at=cell,state=m.block(cell)));continue
            for raw in shapes:
                box=np.asarray(raw)+np.tile(cell,2)
                if overlaps(tri,box[:3],box[3:]):
                    state=m.block(cell);counts[state]+=1;collisions.append(dict(part=part['name'],at=cell,state=state));break
    report=dict(candidate_sha_source=str(source),frozen_world=str(world),world_written=False,pieces=len(meshes),
        colliding_part_cells=len(collisions),counts=dict(counts),collisions=collisions,unknown=unknown)
    output.write_text(json.dumps(report,indent=2),'utf8')
    print('pieces',len(meshes),'colliding part/cells',len(collisions),'unknown',len(unknown),'states',dict(counts),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('world','source','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();audit(a.world,a.source,a.output)
