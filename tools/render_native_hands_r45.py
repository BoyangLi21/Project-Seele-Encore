"""Render exact actual hand submissions; camera/translation only, no pose edits."""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np
from mathutils import Vector

p=argparse.ArgumentParser();p.add_argument('--witness',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
p.add_argument('--hand-focus',action='store_true',help='Keep the arm in scene but frame the actual replacement hand')
p.add_argument('--weapon-context',choices=('cannon','rifle','knife'),help='Include the actually submitted weapon without changing the hand-focused camera')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);a.out=a.out.resolve();a.witness=a.witness.resolve();a.out.mkdir(parents=True,exist_ok=True)
rows=[json.loads(s) for s in a.witness.read_text('utf8').splitlines()]
geometry={r['resource_part']:r for r in rows if r['kind']=='actual_static_part_geometry'}
palettes=[r for r in rows if r['kind']=='final_named_palette'];samples=[palettes[i] for i in dict.fromkeys((0,len(palettes)//2,len(palettes)-1))]
axes=np.array([[1.,0,0],[0,0,-1],[0,1,0]])
receipts=[]
for palette in samples:
 tick=palette['tick'];bones={r['name']:r for r in palette['bones']}
 for side in ['l','r']:
  bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
  hand=bones['hand_'+side];world=np.asarray(palette['model_to_world_column_major']).reshape(4,4).T;hm=np.asarray(hand['final_model_column_major']).reshape(4,4).T
  origin=(world@hm@np.r_[hand['pivot_model'],1])[:3];allpoints=[];focuspoints=[]
  for r in rows:
   if r['kind']!='actual_cpu_submitted_part' or r['tick']!=tick:continue
   weapon=a.weapon_context is not None and r['bone']==a.weapon_context
   if not r['bone'].endswith('_'+side) and not weapon:continue
   pts=np.array(geometry[r['resource_part']]['original_part_xyz']).reshape(-1,3)
   changes=np.asarray(r['submitted_position_changes_index_xyz']).reshape(-1,4)
   for c in changes:pts[int(c[0])]=c[1:]
   pts=(pts+r['part_pivot_authored'])*[-1,1,1]/16;matrix=np.asarray(r['mesh_to_world_column_major']).reshape(4,4).T
   actual=pts@matrix[:3,:3].T+matrix[:3,3];indices=np.asarray(r['actual_world_sample_vertex_indices'],int)
   error=float(np.abs(actual[indices]-np.asarray(r['actual_world_sample_xyz']).reshape(-1,3)).max());assert error<.01
   pts=(actual-origin)@axes.T;allpoints.extend(pts)
   if 'anatomical_hands' in r['resource']:focuspoints.extend(pts)
   mesh=bpy.data.meshes.new(r['bone']);mesh.from_pydata(pts.tolist(),[],np.arange(len(pts)).reshape(-1,3).tolist());mesh.update()
   obj=bpy.data.objects.new(r['bone'],mesh);bpy.context.collection.objects.link(obj)
   mat=bpy.data.materials.new(r['bone']);mat.diffuse_color=(.22,.26,.29,1) if weapon else (.35,.14,.65,1) if r['bone'].startswith('hand_') else (.1,.65,.3,1) if '_tip_' not in r['bone'] and '_distal_' not in r['bone'] else (.1,.5,.85,1) if '_tip_' in r['bone'] else (.95,.45,.1,1);mesh.materials.append(mat)
  pts=np.asarray(focuspoints if a.hand_focus and focuspoints else allpoints);centre=Vector((pts.min(0)+pts.max(0))*.5);span=float(np.ptp(pts,axis=0).max())
  cam=bpy.data.objects.new('Actual hand camera',bpy.data.cameras.new('Actual hand camera'));bpy.context.collection.objects.link(cam);scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=span*1.4
  cam.location=centre+Vector((4,-6,4)).normalized()*span*3;cam.rotation_euler=(centre-cam.location).to_track_quat('-Z','Y').to_euler()
  scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH';scene.world=bpy.data.worlds.new('Native hand diagnostic');scene.world.color=(.09,.11,.14)
  scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100;file=a.out/f'actual_tick{tick}_{side}.png';scene.render.filepath=str(file);bpy.ops.render.render(write_still=True)
  receipts.append(dict(tick=tick,side=side,file=str(file),vertices=len(pts),scope='Exact native original+sparse CPU changes+actual matrix, independently matched18 world samples. Diagnostic colours only; no reauthored pose or replacement geometry.'))
(a.out/'receipt.json').write_text(json.dumps(receipts,indent=2),'utf8')
