"""Isolated exporter trial; do not register its UI/updater or upload project assets."""
from pathlib import Path
import sys,types,importlib,json,traceback
import bpy

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/repair_r43/tool_trials';SOURCE=OUT/'epicfight-blender'
package=types.ModuleType('r43_epic_trial');package.__path__=[str(SOURCE)];sys.modules[package.__name__]=package
exporter=importlib.import_module('r43_epic_trial.export_mc_json')
class Operator:
    def report(self,kind,message):print(sorted(kind),message,flush=True)
results=[]
original_scene=bpy.context.scene
for name in ('eva_candidate','angel_candidate'):
    try:
        # Upstream save_common takes the FIRST armature in scene.objects,
        # regardless of active selection. A single-actor export scene is the
        # required adapter for our paired authoring scene.
        rig=bpy.data.objects[name];scene=bpy.data.scenes.new('export_'+name);scene.collection.objects.link(rig)
        scene.render.fps=original_scene.render.fps;scene.frame_end=original_scene.frame_end;bpy.context.window.scene=scene
        rig.select_set(True);bpy.context.view_layer.objects.active=rig
        file=OUT/(name+'_epic.json')
        status=exporter.save(Operator(),bpy.context,filepath=str(file),export_mesh=False,export_armature=True,
            export_anim=True,armature_format='MAT',animation_format='MAT',bake_animation=True,optimize_keyframes=False,
            export_camera=False,export_only_visible_bones=False)
        data=json.loads(file.read_text()) if file.exists() else None
        names=data['armature']['joints'] if data else []
        assert set(names)=={b.name for b in rig.data.bones if b.use_deform},'Wrong exported actor or missing bones'
        results.append(dict(actor=name,status=sorted(status),keys=list(data) if data else [],bones=len(names),bytes=file.stat().st_size if file.exists() else 0))
    except Exception as error:
        traceback.print_exc();results.append(dict(actor=name,error=repr(error)))
    finally:
        bpy.context.window.scene=original_scene
        if 'scene' in locals():bpy.data.scenes.remove(scene)
(OUT/'epic_export_trial.json').write_text(json.dumps(dict(blender=bpy.app.version_string,source_commit='b9c6844193074f8c21b35513052d61c82cc2c207',
    registration='Core export module only; no updater/UI/preferences modified',results=results,scope='Export schema interoperability; this is not yet a Project SEELE runtime adapter'),indent=2),'utf8')
print(json.dumps(results),flush=True)
