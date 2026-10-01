"""Read real DCC skin failures, preserving vertex/bone provenance."""
from pathlib import Path
import sys,json
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r44/combat/tv_exchange/counter_v2';fixture=json.loads((OUT/'fixture.json').read_text('utf8'));data=next(x for x in fixture['actors']if x['key']=='sachiel');rows=[]
for frame in(1,6,24,35,63,109):
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();obj=bpy.data.objects['sachiel_actual_mesh'].evaluated_get(deps);mesh=obj.to_mesh();points=np.asarray([list(obj.matrix_world@v.co)for v in mesh.vertices]);selected=np.argsort(points[:,2])[:4];obj.to_mesh_clear();bad=[]
    for i in selected:bad.append(dict(vertex=int(i),world=points[i].tolist(),neutral=data['vertices'][i],skin=[dict(bone=data['bones'][slot]['name'],weight=weight)for slot,weight in zip(data['influences'][i],data['weights'][i])if weight>.005]))
    author=bpy.data.objects['sachiel_AUTHOR'].evaluated_get(deps);angles={n:list(author.pose.bones[n].matrix_basis.to_euler())for n in('leg_l','shin_l','foot_l','leg_r','shin_r','foot_r','forearm_r')};rows.append(dict(frame=frame,lowest_actual_skin=bad,signed_blender_basis=angles))
(OUT/'skin_first_offset.json').write_text(json.dumps(rows,indent=2),'utf8');print(json.dumps(rows,indent=2),flush=True)
