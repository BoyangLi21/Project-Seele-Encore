"""Actual mesh negative controls for an offline wrist-to-shin mapping error."""
from pathlib import Path
import argparse,json,sys,math
import bpy,numpy as np
from mathutils import Matrix,Quaternion

ap=argparse.ArgumentParser();ap.add_argument('--raw',type=Path,required=True);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
raw=args.raw.resolve();out=raw/'alias_isolation';out.mkdir(exist_ok=True)
data=json.loads((raw/'fixture.json').read_text('utf8'))['actors'][0];name=data['name']
author=bpy.data.objects[name+'_AUTHOR'];deform=bpy.data.objects[name+'_DEFORM'];mesh=bpy.data.objects[name+'_actual_mesh']
before=json.loads(author['aliases_json']);after=before.copy()
parents={r['name']:r['parent'] for r in data['bones']}
for side in ('l','r'):
    after['wrist_'+side]='forearm_'+side;after['ankle_'+side]='shin_'+side
author.animation_data_clear();deform.animation_data_clear()
for b in author.pose.bones:
    for c in list(b.constraints):b.constraints.remove(c)
names=[r['name'] for r in data['bones']];ids=np.asarray(data['influences']);weights=np.asarray(data['weights']);owner=ids[np.arange(len(ids)),np.argmax(weights,axis=1)]
groups={n:np.flatnonzero(owner==names.index(n)) for n in ('wrist_l','wrist_r','hand_l','hand_r','shin_l','shin_r','ankle_l','ankle_r') if n in names}
results={};actual_vertices={}
for label,aliases in (('incorrect_inherited',before),('correct_anatomical',after)):
    for case,bone in (('neutral',None),('left_forearm_distal_owner','forearm_l'),('left_hand_wrist_flexion','hand_l'),('left_shin_knee_flexion','shin_l')):
        for b in author.pose.bones:b.matrix_basis=Matrix.Identity(4)
        if bone:
            p=author.pose.bones[bone];p.rotation_mode='QUATERNION';p.rotation_quaternion=Quaternion((1,0,0),math.radians(20))
        bpy.context.view_layer.update();solved=author.evaluated_get(bpy.context.evaluated_depsgraph_get())
        transforms={n:solved.pose.bones[n].matrix@author.data.bones[n].matrix_local.inverted() for n in author.data.bones.keys()}
        desired={n:transforms[aliases[n]]@deform.data.bones[n].matrix_local for n in aliases}
        for b in deform.data.bones:
            parent=b.parent;local=b.matrix_local.inverted()@desired[b.name] if parent is None else b.matrix_local.inverted()@parent.matrix_local@desired[parent.name].inverted()@desired[b.name]
            deform.pose.bones[b.name].matrix_basis=local
        bpy.context.view_layer.update();obj=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());evaluated=obj.to_mesh();points=np.asarray([list(obj.matrix_world@v.co) for v in evaluated.vertices]);obj.to_mesh_clear()
        actual_vertices[label+':'+case]={n:[dict(index=int(i),world=points[i].tolist()) for i in selected] for n,selected in groups.items()}
        if case=='neutral':baseline=points.copy();results[label]={}
        else:
            results[label][case]={n:dict(vertices=len(selected),maximum_actual_mesh_displacement_blocks=float(np.linalg.norm(points[selected]-baseline[selected],axis=1).max()) if len(selected) else 0.) for n,selected in groups.items()}
report=dict(source_scene=str(raw/'rokoko_continuous_legs_r44.blend'),actual_geo_parent={n:parents[n] for n in ('wrist_l','wrist_r','ankle_l','ankle_r')},before_alias=before,after_alias=after,
    actual_single_side_mesh_controls=results,actual_reloaded_blender_vertices=actual_vertices,
    scope='R44 private Blender author→alias→deform→evaluated mesh only. Runtime does not read aliases_json; exported per-bone matrices inherit a bad alias if generated from it. No source changes or native submitted vertices are asserted by this offline test.',
    old_delivery_impact='Not established by this test; search generator imports and installed resource provenance separately',native_submitted_vertices=False)
(out/'single_side_alias_controls.json').write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps({k:v for k,v in report.items() if k in ('actual_geo_parent','actual_single_side_mesh_controls','scope')},indent=2))
