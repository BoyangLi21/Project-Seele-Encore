"""Use an actual closed knuckle surface instead of the open palm centroid."""
from pathlib import Path
import json
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/combat/tv_exchange';SOURCE=BASE/'counter_v4';OUT=BASE/'counter_v5';OUT.mkdir(parents=True,exist_ok=True);fixture=json.loads((SOURCE/'fixture.json').read_text('utf8'));data=next(a for a in fixture['actors']if a['key']=='1');names=[b['name']for b in data['bones']];ids=np.asarray(data['influences']);weights=np.asarray(data['weights']);receipt=[]
for side,frame,target_name in[('r',35,'CONTACT_chest'),('l',19,'CONTACT_incoming')]:
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();rig=bpy.data.objects['eva_unit01_DEFORM'].evaluated_get(deps);obj=bpy.data.objects['eva_unit01_actual_mesh'].evaluated_get(deps);mesh=obj.to_mesh();actual=np.asarray([list(obj.matrix_world@v.co)for v in mesh.vertices]);obj.to_mesh_clear();target=Vector(bpy.data.objects[target_name].evaluated_get(deps).matrix_world.translation)
    shoulder=rig.pose.bones['arm_'+side].head;direction=np.asarray((target-shoulder).normalized());bone_slots=[i for i,n in enumerate(names)if n=='hand_'+side or(n.startswith('finger_')and n.endswith('_'+side))];mask=np.isin(ids,bone_slots);coverage=np.where(mask,weights,0).sum(1);eligible=np.flatnonzero(coverage>.9)
    # True submitted closed-fist point nearest the target tangent plane. This
    # selects a fixed vertex owned by the constant .98 closed hand shape.
    delta=actual[eligible]-np.asarray(target);projection=delta@direction;tangent=delta-np.outer(projection,direction);eligible=eligible[np.linalg.norm(tangent,axis=1)<5]
    vertex=int(eligible[np.argmax(actual[eligible]@direction)]);hand_matrix=rig.pose.bones['hand_'+side].matrix@rig.data.bones['hand_'+side].matrix_local.inverted();closed=hand_matrix.inverted()@Vector(actual[vertex]);pivot=Vector(data['hands'][side]['pivot']);old=data['hands'][side]['surface'];data['hands'][side].update(surface=list(closed),offset=list(closed-pivot),contact_vertex=vertex,contact_owner=names[ids[vertex,np.argmax(weights[vertex])]],contact_scope='Actual constant closed-fist vertex, calibrated from saved Blender skin; no finger capture inferred.')
    receipt.append(dict(side=side,source_frame=frame,vertex=vertex,owner=data['hands'][side]['contact_owner'],old_palm_centroid=old,new_closed_surface=list(closed),actual_source_point=actual[vertex].tolist(),target=list(target),source_point_along_attack=float((actual[vertex]-np.asarray(target))@direction)))
(OUT/'fixture.json').write_text(json.dumps(fixture,separators=(',',':')),'utf8');(OUT/'clenched_contact_receipt.json').write_text(json.dumps(dict(source_scene=str(SOURCE/'tv_exchange_blocking_r44.blend'),contacts=receipt,scope='Candidate source/actual mesh correction, not native/artistic approval.'),indent=2),'utf8');print(json.dumps(receipt,indent=2),flush=True)
