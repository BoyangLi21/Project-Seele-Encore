"""Trace actual emitted face ownership back to original OBJ/UV topology."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from build_rigged_angels_r10 import obj
ap=argparse.ArgumentParser();ap.add_argument('--rig',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True);rig=json.loads(args.rig.read_text());path=Path(rig['source']);v,uv,n,faces,mats,textures=obj(path)
def components(index,material=None):
    count=len(v)if index==0 else len(uv);parent=list(range(count))
    def find(k):
        while parent[k]!=k:parent[k]=parent[parent[k]];k=parent[k]
        return k
    for face,mat in zip(faces,mats):
        if material is None or mat==material:
            for point in face[1:]:parent[find(point[index])]=find(face[0][index])
    result={}
    for i,(face,mat)in enumerate(zip(faces,mats)):
        if material is None or mat==material:result.setdefault(find(face[0][index]),[]).append(i)
    return result
physical=components(0);uvgroups={m:components(1,m)for m in sorted(set(mats))};emitted=[i for i,m in enumerate(mats)if not m.startswith('6b823')];focus_source=emitted[9580//4];physical_id=next(k for k,indices in physical.items()if focus_source in indices);uv_id=next(k for k,indices in uvgroups[mats[focus_source]].items()if focus_source in indices);rows=[]
for material,groups in uvgroups.items():
    for group,indices in groups.items():
        pts=v[[a[0]for i in indices for a in faces[i]]];texcoords=uv[[a[1]for i in indices for a in faces[i]]];rows.append(dict(material=material,uv_component=group,source_faces=indices,faces=len(indices),source_aabb=[pts.min(0).tolist(),pts.max(0).tolist()],uv_aabb=[texcoords.min(0).tolist(),texcoords.max(0).tolist()],physical_components=sorted(k for k,part in physical.items()if any(i in part for i in indices)),contains_actual_face9580=focus_source in indices))
result=dict(source=str(path.resolve()),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),actual_emitted_face=9580,original_source_face=focus_source,physical_component_id=physical_id,physical_component_faces=len(physical[physical_id]),uv_component_id=uv_id,material=mats[focus_source],original_vertex_indices=[a[0]for a in faces[focus_source]],original_vertices=v[[a[0]for a in faces[focus_source]]].tolist(),original_uv=uv[[a[1]for a in faces[focus_source]]].tolist(),groups=rows,scope='Original physical vertex connectivity, separate per-material UV-index connectivity and exact four-way emitted subdivision ancestry. Connectivity alone is not anatomical hard-plate ownership.',default_promoted=False)
(args.out/'source_part_topology.json').write_text(json.dumps(result,indent=2));np.savez_compressed(args.out/'original_geometry_with_parts.npz',vertices_source=v,triangles=np.asarray([[p[0]for p in face]for face in faces]),uv_per_triangle=np.asarray([[uv[p[1]]for p in face]for face in faces]),face_material=np.asarray(mats),face_uv_component=np.asarray([next(k for k,indices in uvgroups[m].items()if i in indices)for i,m in enumerate(mats)]),physical_component=np.asarray([next(k for k,indices in physical.items()if i in indices)for i in range(len(faces))]));print(json.dumps({k:v for k,v in result.items()if k!='groups'},indent=2))
