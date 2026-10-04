"""Measure contact depth on actual posed fingertip pads, without changing meshes."""
from pathlib import Path
import argparse, json, sys
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True)
p.add_argument('--posed',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--side',choices=('l','r'),default='r')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
c=json.loads((a.candidate/'hand_rig_contract.json').read_text('utf8'))
m=json.loads((a.candidate/f"eva_unit0{c['rig']}_anatomical_hands_r45.mesh.json").read_text('utf8'))
d=np.load(a.posed);vertices=d['vertices'];faces=d['faces'];labels=d['labels']
palm=BVHTree.FromPolygons([Vector(x)for x in vertices],faces[labels==-1].tolist(),all_triangles=True)
normal=Vector(c['hands'][a.side]['palmar_normal_bind']);report=[]
for digit in ('index','middle','ring','little'):
 name=c['hands'][a.side]['digits'][digit]['joints'][-1]['name']
 weights=np.asarray(m['jointSkins']['hand_'+a.side]['influences'][name])
 values=[]
 for i in np.flatnonzero(weights>.8):
  at=Vector(vertices[i]);hit,n,face,distance=palm.ray_cast(at+normal, -normal,2)
  if hit is None:continue
  depth=(hit-at).dot(normal)
  if depth>0:values.append((int(i),float(depth)))
 report.append(dict(digit=digit,penetrating_pad_vertices=len(values),
                    maximum_depth_model=max((v[1]for v in values),default=0),
                    examples=sorted(values,key=lambda v:-v[1])[:10]))
a.out.write_text(json.dumps(dict(measurements=report,mesh_unchanged=True,
 scope='Directional contact depth; requires topology/visual review, not a collision certificate'),indent=2),'utf8')
print(json.dumps(report))
