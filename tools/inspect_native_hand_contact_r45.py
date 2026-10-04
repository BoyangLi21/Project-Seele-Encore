"""Still inspection of exact native hand/weapon positions; no animation/video."""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np
from mathutils import Vector,Matrix

p=argparse.ArgumentParser();p.add_argument('--witness',type=Path,required=True);p.add_argument('--contract',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--back',action='store_true');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
c=json.loads(a.contract.read_text(encoding='utf8'));palettes=[];static={}
for line in a.witness.open(encoding='utf8'):
 r=json.loads(line)
 if r['kind']=='final_named_palette':palettes.append(r)
 elif r['kind']=='actual_static_part_geometry':static[r['resource_part']]=r
armed=[r for r in palettes if r['actual_owner_inputs'].get('weapon')==4]
assert armed,'No actual armed sample; do not inspect warm-up as a gun grip'
selected={label:min(armed,key=lambda r:(abs(r['stance']-value),-r['tick'])) for label,value in [('standing',0),('crouch',1),('prone',3)]};ticks={r['tick']for r in selected.values()};parts={t:[]for t in ticks}
for line in a.witness.open(encoding='utf8'):
 r=json.loads(line)
 if r['kind']=='actual_cpu_submitted_part'and r['tick']in ticks:parts[r['tick']].append(r)
AX=np.array([[1,0,0],[0,0,-1],[0,1,0]]);receipt=[]
for label,pose in selected.items():
 bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;ms=np.asarray(pose['model_to_world_column_major']).reshape(4,4).T;origin=ms[:3,3];hand_points={};count=0;maximum=0
 for row in parts[pose['tick']]:
  if row['bone']not in ['hand_l','hand_r','cannon','knife']:continue
  g=static[row['resource_part']];points=np.asarray(g['original_part_xyz']).reshape(-1,3).copy()
  for v in np.asarray(row['submitted_position_changes_index_xyz']).reshape(-1,4):points[int(v[0])]=v[1:]
  points=(points+row['part_pivot_authored'])*[-1,1,1]/16;m=np.asarray(row['mesh_to_world_column_major']).reshape(4,4).T;world=points@m[:3,:3].T+m[:3,3];ids=row['actual_world_sample_vertex_indices'];error=float(np.abs(world[ids]-np.asarray(row['actual_world_sample_xyz']).reshape(-1,3)).max());maximum=max(maximum,error);assert error<.01
  shown=(world-origin)@AX.T
  if row['bone'].startswith('hand_'):hand_points[row['bone']]=shown
  unique,inv=np.unique(np.round(shown,5),axis=0,return_inverse=True);mesh=bpy.data.meshes.new(row['bone']);mesh.from_pydata(unique.tolist(),[],inv.reshape(-1,3).tolist());mesh.update();ob=bpy.data.objects.new(row['bone'],mesh);bpy.context.collection.objects.link(ob);mat=bpy.data.materials.new(row['bone']);mat.diffuse_color=(.31,.15,.47,1)if row['bone'].startswith('hand_')else(.22,.26,.20,1);mesh.materials.append(mat)
  for f in mesh.polygons:f.use_smooth=True
  count+=1
 assert 'hand_l'in hand_points and'hand_r'in hand_points and count>=3,'No actual weapon/hand submission in selected sample'
 for side in ['l','r']:
  points=hand_points['hand_'+side];centre=Vector((points.min(0)+points.max(0))*.5);span=float(np.ptp(points,axis=0).max());bone=next(b for b in pose['bones']if b['name']=='hand_'+side);bm=np.asarray(bone['final_model_column_major']).reshape(4,4).T;rotation=ms[:3,:3]@bm[:3,:3];normal=Vector(AX@rotation@np.asarray(c['hands'][side]['palmar_normal_bind'])).normalized();up=-Vector(AX@rotation@np.asarray(c['hands'][side]['longitudinal_bind'])).normalized();right=up.cross(normal).normalized();direction=(normal*(-1 if a.back else 1)+right*.5+up*.15).normalized()
  camera=bpy.data.objects.new('Native contact camera',bpy.data.cameras.new('Native contact camera'));bpy.context.collection.objects.link(camera);scene.camera=camera;camera.data.type='ORTHO';camera.data.ortho_scale=span*1.7;camera.location=centre+direction*span*3;cr=up.cross(direction).normalized();cu=direction.cross(cr).normalized();camera.rotation_euler=Matrix((cr,cu,direction)).transposed().to_euler();scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.world=bpy.data.worlds.new('Diagnostic');scene.world.color=(.12,.13,.15);scene.render.resolution_x=900;scene.render.resolution_y=760;scene.render.resolution_percentage=100;file=a.out/f'{label}_{side}.png';scene.render.filepath=str(file);bpy.ops.render.render(write_still=True)
  receipt.append(dict(stage=label,stance=pose['stance'],side=side,tick=pose['tick'],exact_world_readback_error=maximum,file=str(file),scope='Exact actual CPU geometry and actual native transforms; matte diagnostic materials, not game shader/art acceptance'))
(a.out/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
