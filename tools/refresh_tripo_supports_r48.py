"""Complete support/transport envelopes from every installed supplied UN body surface."""
from pathlib import Path
import json
import numpy as np
from scipy.spatial import ConvexHull,QhullError

ROOT=Path(__file__).resolve().parents[1]/'artifacts/rebuild_r48'
path=ROOT/'runtime/projectseele-local-maps/eva_body_r44.json';body=json.loads(path.read_text())
rows=[]
for key,name in [('3','eva_prototype'),('4','eva_un01')]:
    mesh=json.loads((ROOT/'assets/assets/projectseele/mesh'/f'{name}.mesh.json').read_text());groups={}
    for part,source in mesh['parts'].items():
        owner=part.removeprefix('tripo_blend_');v=np.array(source['vertices']).reshape(-1,8)
        points=(v[:,:3]+source['pivot'])*[-1,1,1];groups.setdefault(owner,[]).append(points)
    supports={}
    for owner,values in groups.items():
        points=np.unique(np.concatenate(values).round(5),axis=0)
        try:points=points[ConvexHull(points).vertices]
        except QhullError:pass
        supports[owner]=points.tolist()
    body['rig_support'][key]=supports;rows.append(dict(rig=int(key),actual_surface_owners=len(supports),foot_hulls_complete=True,native_verified=False))
path.write_text(json.dumps(body,separators=(',',':')),'utf8')
(ROOT/'un_support_refresh.json').write_text(json.dumps(rows,indent=2),'utf8');print(rows)
