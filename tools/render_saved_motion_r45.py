"""Render saved Blender animation stills; never label them native screenshots."""
from pathlib import Path
import argparse,json,sys,hashlib
import bpy

p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
p.add_argument('--frames',type=int,nargs='+',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
assert a.out.is_absolute(),'Blender can change process cwd; use an explicit absolute artifact path'
assert not a.out.exists();a.out.mkdir(parents=True)
source=Path(bpy.data.filepath);before=hashlib.sha256(source.read_bytes()).hexdigest()
scene=bpy.context.scene
engines={item.identifier for item in scene.render.bl_rna.properties['engine'].enum_items}
scene.render.engine='BLENDER_EEVEE' if 'BLENDER_EEVEE' in engines else 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x=1100;scene.render.resolution_y=760;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
frames=[]
for frame in a.frames:
    assert scene.frame_start<=frame<=scene.frame_end
    scene.frame_set(frame);bpy.context.view_layer.update()
    path=a.out/f'offline_blender_{frame:04}.png';scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    frames.append({'frame':frame,'file':str(path.resolve())})
assert before==hashlib.sha256(source.read_bytes()).hexdigest()
(a.out/'receipt.json').write_text(json.dumps({'source_blend':str(source),'source_sha256':before,
    'images':frames,'renderer':'Blender Eevee; saved source retarget before contact solving',
    'native_game_images':False,'art_accepted':False,'source_unchanged':True},indent=2),'utf8')
