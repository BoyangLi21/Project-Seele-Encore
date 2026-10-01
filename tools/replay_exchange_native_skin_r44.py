"""Private preview of weighted-Angel first-slot DQ from exported poses.

Keeps source armatures and editable controls. Replaces only the displayed NPC
mesh with keyed vertex samples; no production assets or Java are changed.
"""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np
from mathutils import Matrix,Quaternion

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.out.resolve()
# Reuse the independent decoder/skin functions without executing its audit.
module=ROOT/'tools/audit_exchange_export_skin_r44.py';source=module.read_text('utf8');namespace=dict(__file__=str(module));exec(source[:source.index('\nfor frame in (1,6,19')],namespace)
fixture=json.loads((out/'fixture.json').read_text('utf8'));export=json.loads((out/'paired_runtime_pose_candidate.json').read_text('utf8'));data=next(a for a in fixture['actors']if a['key']=='sachiel');role=export['roles']['sachiel'];mapping=namespace['mapping'];inverse=namespace['inverse'];original=bpy.data.objects['sachiel_actual_mesh'];mesh=original.data.copy();obj=bpy.data.objects.new('sachiel_export_first_slot_DQ_preview',mesh);bpy.context.collection.objects.link(obj);obj.shape_key_add(name='Basis');positions=np.asarray(data['vertices']);ids=np.asarray(data['influences']);weights=np.asarray(data['weights']);checks=[]
for frame,pose in enumerate(role['frames'],1):
    matrices=namespace['decode'](role,pose);transforms=[matrices[b['name']]@mapping@np.linalg.inv(np.asarray(b['neutral_model']))@inverse for b in data['bones']];points=namespace['skin'](positions,transforms,ids,weights,first_slot=True);key=obj.shape_key_add(name=f'exported_{frame:04d}');key.data.foreach_set('co',points.reshape(-1));key.value=0;key.keyframe_insert('value',frame=frame-1);key.value=1;key.keyframe_insert('value',frame=frame);key.value=0;key.keyframe_insert('value',frame=frame+1);checks.append(dict(frame=frame,minimum_z=float(points[:,2].min())))
original.hide_render=True;original.hide_set(True);obj['scope']='Offline exported pose replay using weighted Angel RiggedAngelLayer first-slot quaternion reference. Not a running Java/native/GPU capture; wrap and grounded support branches excluded.';obj['source_mesh_sha256']=data['mesh_sha256'];bpy.context.scene['native_skin_preview_scope']=obj['scope'];bpy.context.scene.frame_set(35)
target=out/'first_slot_skin_preview.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target));(out/'first_slot_skin_preview_receipt.json').write_text(json.dumps(dict(scene=str(target),frames=len(checks),original_mesh_written=False,production_resources_installed=False,scope=obj['scope'],minimum_whole_mesh_z=min(r['minimum_z']for r in checks),samples=checks),indent=2),'utf8');print('Saved export/actual-renderer-rule preview',target)
