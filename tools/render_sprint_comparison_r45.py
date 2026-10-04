"""Same-camera Blender stills for the preserved-run/new-sprint comparison."""
from pathlib import Path
import argparse,copy,json,sys
import bpy
from mathutils import Matrix,Vector

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=a.out.resolve();assert (out/'poses.json').is_file()
old_argv=sys.argv;sys.argv=[str(root/'tools/build_tv_exchange_r44.py'),'--','--out',str(out)]
import build_tv_exchange_r44 as dcc
sys.argv=old_argv
fixture=json.loads((out/'fixture.json').read_text('utf8'));poses=json.loads((out/'poses.json').read_text('utf8'))
bpy.ops.wm.read_factory_settings(use_empty=True);scene=dcc.setup_scene();scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=1000;scene.render.resolution_y=850;scene.render.resolution_percentage=100
scene.camera.location=(85,105,50);target=Vector((0,0,30))
scene.camera.rotation_euler=(target-scene.camera.location).to_track_quat('-Z','Y').to_euler();scene.camera.data.ortho_scale=73
rig,obj=dcc.deform_rig(fixture['actors'][0]);images=[]
for role,clip in poses.items():
    for index in (0,12,24,36):
        transforms={n:Matrix(v)for n,v in clip['frames'][index].items()}
        desired={b.name:transforms[b.name]@b.matrix_local for b in rig.data.bones}
        for bone in rig.data.bones:
            local=bone.matrix_local.inverted()@desired[bone.name] if bone.parent is None else bone.matrix_local.inverted()@bone.parent.matrix_local@desired[bone.parent.name].inverted()@desired[bone.name]
            rig.pose.bones[bone.name].matrix_basis=local
        bpy.context.view_layer.update();path=out/f'{role}_{index:03}_OFFLINE.png';scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True);images.append(str(path))
(out/'render_receipt.json').write_text(json.dumps({'images':images,'same_camera_and_mesh':True,'native_game_images':False,'art_accepted':False},indent=2),'utf8')
